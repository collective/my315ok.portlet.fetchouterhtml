from zope.interface import implements
from plone.portlets.interfaces import IPortletDataProvider
from plone.app.portlets.portlets import base
from zope.component import getMultiAdapter
from zope import schema
from zope.formlib import form
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.vocabularies.catalog import SearchableTextSourceBinder
from plone.app.form.widgets.uberselectionwidget import UberSelectionWidget
from Products.ATContentTypes.interface import IATFolder

import re
from datetime import datetime,timedelta

from my315ok.portlet.fetchouterhtml import FetchOuterPortletMessageFactory as _
from plone.portlet.collection import PloneMessageFactory as _a

fmt = '%Y/%m/%d %H:%M:%S'

from plone.memoize.instance import memoize
import socket
import time
import urllib2
##import xml.dom.minidom
__version__ = 3.1
try:
    from BeautifulSoup import BeautifulSoup,SoupStrainer
except:
    print "ERROR: could not import BeautifulSoup Python module"
    print
    print "You can download BeautifulSoup from the Python Cheese Shop at"
    print "http://cheeseshop.python.org/pypi/BeautifulSoup/"
    print "or directly from http://www.crummy.com/software/BeautifulSoup/"
    print
    raise

##try:
##    import simplejson
##except:
##    print "ERROR: could not import simplejson module"
##    print
##    print "Since version 1.5.0, DeliciousAPI requires the simplejson module."
##    print "You can download simplejson from the Python Cheese Shop at"
##    print "http://pypi.python.org/pypi/simplejson"
##    print
##    raise

class FetchOutWebPage(object):
    """
    This class provides a custom, unofficial API to the Delicious.com service.

    Instead of using just the functionality provided by the official
    Delicious.com API (which has limited features), this class retrieves
    information from the Delicious.com website directly and extracts data from
    the Web pages.

    Note that Delicious.com will block clients with too many queries in a
    certain time frame (similar to their API throttling). So be a nice citizen
    and don't stress their website.

    """

    def __init__(self,
                    http_proxy="",
                    tries=2,
                    wait_seconds=3,
                    user_agent="Firefox/%s" % __version__,
                    timeout=30,
        ):
        """Set up the API module.

        @param http_proxy: Optional, default: "".
            Use an HTTP proxy for HTTP connections. Proxy support for
            HTTPS is not available yet.
            Format: "hostname:port" (e.g., "localhost:8080")
        @type http_proxy: str

        @param tries: Optional, default: 3.
            Try the specified number of times when downloading a monitored
            document fails. tries must be >= 1. See also wait_seconds.
        @type tries: int

        @param wait_seconds: Optional, default: 3.
            Wait the specified number of seconds before re-trying to
            download a monitored document. wait_seconds must be >= 0.
            See also tries.
        @type wait_seconds: int

        @param user_agent: Optional, default: "DeliciousAPI/<version>
            (+http://www.michael-noll.com/wiki/Del.icio.us_Python_API)".
            The User-Agent HTTP Header to use when querying Delicous.com.
        @type user_agent: str

        @param timeout: Optional, default: 30.
            Set network timeout. timeout must be >= 0.
        @type timeout: int

        """
        assert tries >= 1
        assert wait_seconds >= 0
        assert timeout >= 0
        self.http_proxy = http_proxy
        self.tries = tries
        self.wait_seconds = wait_seconds
        self.user_agent = user_agent
        self.timeout = timeout
        socket.setdefaulttimeout(self.timeout)

    def _query(self, host="http://delicious.com/", user=None, password=None):
        """Queries Delicious.com for information, specified by (query) path.

        @param path: The HTTP query path.
        @type path: str

        @param host: The host to query, default: "delicious.com".
        @type host: str

        @param user: The Delicious.com username if any, default: None.
        @type user: str

        @param password: The Delicious.com password of user, default: None.
        @type password: unicode/str

        @param use_ssl: Whether to use SSL encryption or not, default: False.
        @type use_ssl: bool

        @return: None on errors (i.e. on all HTTP status other than 200).
            On success, returns the content of the HTML response.

        """
        opener = None
        handlers = []

        # add HTTP Basic authentication if available
        if user and password:
            pwd_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            pwd_mgr.add_password(None, host, user, password)
            basic_auth_handler = urllib2.HTTPBasicAuthHandler(pwd_mgr)
            handlers.append(basic_auth_handler)

        # add proxy support if requested
        if self.http_proxy:
            proxy_handler = urllib2.ProxyHandler({'http': 'http://%s' % self.http_proxy})
            handlers.append(proxy_handler)

        if handlers:
            opener = urllib2.build_opener(*handlers)
        else:
            opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', self.user_agent)]

        data = None
        tries = self.tries       
        url = host
#        url = "http://list.mp3.baidu.com/index.html"

        while tries > 0:
            try:
                f = opener.open(url)
                data = f.read()
                f.close()
                break
            except urllib2.HTTPError, e:                
                break
            except urllib2.URLError, e:
                time.sleep(self.wait_seconds)
            except socket.error, msg:
                # sometimes we get a "Connection Refused" error
                # wait a bit and then try again
                time.sleep(self.wait_seconds)         
            tries -= 1
        return data

    def _tidysrc(self,data,srccode):
        """tidy scribe the html src"""

        try:
            from tidylib import tidy_document
            BASE_OPTIONS = {
    "output-xhtml": 1,     # XHTML instead of HTML4
    "indent": 1,           # Pretty; not too much of a performance hit
    "tidy-mark": 0,        # No tidy meta tag in output
    "wrap": 0,             # No wrapping
    "alt-text": "",        # Help ensure validation
    "doctype": 'strict',   # Little sense in transitional for tool-generated markup...
    "force-output": 1,     # May not get what you expect but you will get something
    "char-encoding":'utf-8',
    "input-encoding":srccode,
    "output-encoding":'utf-8',
    }
            if not isinstance(data, unicode):                
                try:
                    data = data.decode(srccode)
                except:
                    pass
            doc, errors = tidy_document(data,options={'numeric-entities':1})
            return doc
        except:
            return data
        
    def _extract_data(self,data,tag=None,cssid=None,cssclass=None,attrs=None,regexp=None,index=0):
        """
        Extracts user bookmarks from a URL's history page on Delicious.com.

        The Python library BeautifulSoup is used to parse the HTML page.

        @param data: The HTML source of a URL history Web page on Delicious.com.
        @type data: str

        @return: list of user bookmarks of the corresponding URL

        """
        
#        cssclass = "song"
#        cssid = "newsTable0"
#        tag = "div"
#        import pdb
#        pdb.set_trace()        
        
        if cssid:   
            searchconstrain = SoupStrainer(tag, id=cssid)
        elif cssclass:
            searchconstrain = SoupStrainer(tag, attrs={"class":cssclass})            
        else:
            if  isinstance(attrs, unicode):
                try:
                    attrs = attrs.encode('utf-8')
                    regexp = regexp.encode('utf-8')
                except:
                    pass                
            searchconstrain = SoupStrainer(tag, attrs={attrs:re.compile(regexp)})

        soup = BeautifulSoup(data,parseOnlyThese=searchconstrain)
        rslist = [ tp for tp in soup ]
        return rslist[index]


class IFetchOuterPortlet(IPortletDataProvider):
    """A portlet

    It inherits from IPortletDataProvider because for this portlet, the
    data that is being rendered and the portlet assignment itself are the
    same.
    """
    header = schema.TextLine(title=_a(u"Portlet header"),
                             description=_a(u"Title of the rendered portlet"),
                             required=True)

    show_more = schema.Bool(title=_a(u"Show more... link"),
                       description=_a(u"If enabled, a more... link will appear in the footer of the portlet, "
                                      "linking to the underlying Collection."),
                       required=False,
                       default=False)
    isfilter = schema.Bool(title=_(u"tidy html"),
                       description=_(u"If enabled, html src will using tidy lib to filter its content."),
                       required=False,
                       default=False)
    targeturi = schema.URI(title=_(u"URI"),
                       description=_(u"Specify the url of the target website."),
                       required=True) 
    interval = schema.Int(title=_(u"interval"),
                       description=_(u"Specify the duration for using fresh page,in hours."),
                       default=24,
                       required=True) 
           
    username = schema.TextLine(title=_(u"username"),
                       description=_(u"Specify your username in target website."),
                        required=False
                       )
    passwd = schema.TextLine(title=_(u"passwd"),
                       description=_(u"Specify your password in target website."),
                        required=False
                       )
    tag = schema.TextLine(title=_(u"html tag"),
                       description=_(u"the html tag of outer source that you will locate."),                                      
                       required=True)
    
    cssid = schema.TextLine(title=_(u"outer css id"),
                       description=_(u"the css id of outer source that you will locate."),
                        required=False
                      )
    cssclass = schema.TextLine(title=_(u"css class of the outer selector"),
                       description=_(u"the child css class selector of outer source"),
                        required=False
                      )
    attrs = schema.TextLine(title=_(u"attributes of html tag"),
                       description=_(u"specify the attributes of will be fetched html tag"),
                        required=False
                      )
    regexp = schema.TextLine(title=_(u"regular expression"),
                       description=_(u"speciy the attributes matched regular expression"),
                        required=False
                      )
    index = schema.Int(title=_(u"index"),
                       description=_(u"If return multiple info block,specify the index number of we fetch that one block."),
                       default = 0,
                       required=True)
    codec = schema.TextLine(title=_(u"char code"),
                       description=_(u"source html page char code"),
                       required=True,
                       default = u"utf-8"
                      )

    innerid = schema.TextLine(title=_(u"inner css id"),
                       description=_(u"the css id that you need load html to here."),
                        required=True
                      )    

    
    target_folder = schema.Choice(title=_a(u"Target folder"),
                                  description=_a(u"Find the folder which provides the items to list"),
                                  required=True,
                                  source=SearchableTextSourceBinder({'object_provides' : IATFolder.__identifier__},
                                                                    default_query='path:'))
    tmpdocid = schema.TextLine(title=_(u"doc id"),
                       description=_(u"the generated doc id that using for cache out html source."),
                        required=True
                      )

class Assignment(base.Assignment):
    """Portlet assignment.

    This is what is actually managed through the portlets UI and associated
    with columns.
    """

    implements(IFetchOuterPortlet)

    # TODO: Set default values for the configurable parameters here

    header = u""
    show_more = False
    isfilter = False
    targeturi = u""
    tag = u""
    username = u""
    interval = 5
    index = 0
    passwd = u""
    innerid = u""
    cssid = u""
    tmpdocid = u""
    cssclass = u""
    codec = u"utf-8"
    target_folder = None
    attrs = None
    regexp = None
   
    def __init__(self,header=u"",index=0,show_more=False,isfilter=False,\
                 targeturi=None,interval=5,target_folder=None,tag=None,username=None,\
                 passwd=None,innerid=None,cssid=None,tmpdocid=None,cssclass=None,\
                 attrs=None,regexp=None,codec=None):
        self.header = header
        self.show_more = show_more
        self.isfilter = isfilter
        self.targeturi = targeturi
        self.tag = tag
        self.interval = interval
        self.index = index
        self.target_folder = target_folder
        self.username = username
        self.passwd = passwd
        self.innerid = innerid
        self.cssid = cssid
        self.tmpdocid = tmpdocid
        self.cssclass = cssclass
        self.attrs = attrs
        self.regexp = regexp
        self.codec = codec

    @property
    def title(self):
        """This property is used to give the title of the portlet in the
        "manage portlets" screen.
        """
        return  self.header


class Renderer(base.Renderer):
    """Portlet renderer.

    This is registered in configure.zcml. The referenced page template is
    rendered, and the implicit variable 'view' will refer to an instance
    of this class. Other methods can be added and referenced in the template.
    """

    render = ViewPageTemplateFile('fetchouterportlet.pt')
    
    def available(self):
        return len(self.result())
  
    def isfetch(self,id):
        from time import mktime
        container = self.target_folder()
        if id == None:
            return 1
        obj = getattr(container,id,None)
        if obj == None: 
            return 1       
        #imevalue = self.folder.doc.modified()
        timevalue = obj.modified()        
        
        di = time.strptime(timevalue.strftime(fmt),fmt)
        dt = datetime.fromtimestamp(mktime(di))

        now =   datetime.now()
        if (now - dt) > timedelta(hours = self.data.interval):
            return 1        
        return 0       
    
    def target_baseurl(self):
        tmp = self.data.targeturi
        g = tmp.split("/")
        baseurl = g[0] + "//" + g[2]
        return baseurl        
        
    def portlet_header(self):        
        return  self.data.header    

    def target_folder(self):
        path = self.data.target_folder
        if not path:
            return None
        if path.startswith('/'):
            path = path[1:]        
        if not path:
            return None
        portal_state = getMultiAdapter((self.context, self.request), name=u'plone_portal_state')
        portal = portal_state.portal()
        return portal.unrestrictedTraverse(path, default=None)    
    
    @memoize
    def get_htmlsrc(self):
#        import pdb
#        pdb.set_trace()
        data = self.data
        results = []               
        dapi = FetchOutWebPage()
        srccode = data.codec
        filter = data.isfilter
        gotdata = dapi._query(data.targeturi)
        if gotdata:
            if filter:                
                htmlsource = dapi._extract_data(dapi._tidysrc(gotdata,srccode),data.tag,data.cssid,data.cssclass,\
                                                data.attrs,data.regexp,data.index)
            else:
                htmlsource = dapi._extract_data(gotdata,data.tag,data.cssid,data.cssclass,\
                                                data.attrs,data.regexp,data.index)                 
            return htmlsource
        else:
            return results
            
    @memoize
    def result(self):

        try:
            return self.outer(self.data.tmpdocid)
        except:
            return u''
        
    @memoize        
    def prettyformat(self):
        """transform the relative url to absolute url"""
        
        import re

        html = self.get_htmlsrc()
        if type(html) == type([]):
            html = html[0]
        if type(html) != type(""):
            try:
                html = str(html)
            except:
                html = html.__str__()
            
        tmp = BeautifulSoup(html)
        base = self.target_baseurl()
#        aitems = tmp.findAll("a",href=re.compile("^\/"))
        aitems = tmp.findAll("a",href=re.compile("^[^hH]"))
        for i in aitems:
            u = i['href']
            if u[0] != '/':
                i['href'] = base  + '/' + u
            else:                
                i['href'] = base  + u
#        imgitems = tmp.findAll("img",src=re.compile("^\/"))
        imgitems = tmp.findAll("img",src=re.compile("^[^hH]"))
        for j in imgitems:
            v = j['src']
            if v[0] != '/':
                j['src'] = base  + '/' + v
            else:                
                j['src'] = base  + v
        return tmp                        
        
        
    def outer(self,id):
        if self.isfetch(id):
            try:                
                tmp = self.prettyformat()
                if type(tmp) == type([]):
                    tmp = tmp[0]
                try:
                    tmp = str(tmp)
                except:
                    tmp = tmp.__str__()
                self.store_tmp_content(id, tmp)
                return tmp                
            except:
                return self.fetch_tmp_content(id)
        else:
                
            return self.fetch_tmp_content(id)
            
    @memoize
    def fetch_tmp_content(self,id):
        container = self.target_folder()
        try:
            obj = container[id]
        except:
            return u""
        cached = obj.getText()
        return cached       
            
       
    def store_tmp_content(self,id,content):

        container = self.target_folder()
        if id == None:
            return
        obj = getattr(container,id,None)
        if obj == None:           
            container.invokeFactory(type_name="Document", id=id)
            obj = container[id]      
        obj.setText(content)
        obj.setTitle(id)
        obj.setModificationDate(datetime.now().strftime(fmt))

class AddForm(base.AddForm):
    """Portlet add form.

    This is registered in configure.zcml. The form_fields variable tells
    zope.formlib which fields to display. The create() method actually
    constructs the assignment that is being added.
    """
    form_fields = form.Fields(IFetchOuterPortlet)
    form_fields['target_folder'].custom_widget = UberSelectionWidget
    
    label = _a(u"Add Collection Portlet")
    description = _a(u"This portlet display a listing of items from a Collection.")

    def create(self, data):
        return Assignment(**data)



class EditForm(base.EditForm):
    """Portlet edit form.

    This is registered with configure.zcml. The form_fields variable tells
    zope.formlib which fields to display.
    """
    form_fields = form.Fields(IFetchOuterPortlet)
    form_fields['target_folder'].custom_widget = UberSelectionWidget

    label = _a(u"Edit Collection Portlet")
    description = _a(u"This portlet display a listing of items from a Collection.")
