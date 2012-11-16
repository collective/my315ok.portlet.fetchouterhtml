from zope.component import getUtility, getMultiAdapter

from DateTime import DateTime
from datetime import date
from datetime import timedelta

from plone.portlets.interfaces import IPortletType
from plone.portlets.interfaces import IPortletManager
from plone.portlets.interfaces import IPortletAssignment
from plone.portlets.interfaces import IPortletDataProvider
from plone.portlets.interfaces import IPortletRenderer

from plone.app.portlets.storage import PortletAssignmentMapping

from my315ok.portlet.fetchouterhtml import fetchouterportlet

from my315ok.portlet.fetchouterhtml.tests.base import TestCase
from zope.dublincore.interfaces import ICMFDublinCore 


class TestPortlet(TestCase):

    def afterSetUp(self):
        self.setRoles(('Manager', ))    
        self.folder.invokeFactory('Document', id='doc')
        self.folder.doc.manage_permission(
            'View', ['Manager'], acquire=0)
        self.folder.doc.setText("<div>create html from python</div>")
        

    def test_portlet_type_registered(self):
        
        self.assertEquals(self.folder.doc.getText(),
                          "<div>create html from python</div>")
       # tmp = self.folder.doc.getModificationDate()
        then = self.folder.doc.modified()
        import pdb
        pdb.set_trace()
        di = timedelta(hours = 24)
        
        now =   DateTime()
       
        result = (now - then) > di.seconds
        #timevalue = tmp + dd
        
        self.assertEquals(result,True)
        

   



        # TODO: Test output


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestPortlet))
    #suite.addTest(makeSuite(TestRenderer))
    return suite
