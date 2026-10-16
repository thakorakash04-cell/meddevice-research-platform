import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from workspace_store import Store

class WorkspaceUITests(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        st.cache_data.clear()
        self.tmp=tempfile.TemporaryDirectory()
        self.url='sqlite:///'+str(Path(self.tmp.name)/'ui.db')
        self.env=patch.dict(os.environ,{'DATABASE_URL':self.url,'ADMIN_USERNAME':'admin_user','ADMIN_PASSWORD':'Test-only-admin-password!123'})
        self.env.start()
        self.store=Store(self.url);self.store.bootstrap_admin('admin_user','Test-only-admin-password!123')
        self.admin=self.store.login('admin_user','Test-only-admin-password!123')
        self.store.create_viewer(self.admin,'viewer_user','Test-only-viewer-password!123')
    def tearDown(self):
        self.env.stop();self.tmp.cleanup()
    def signed_in(self,username,password):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        self.assertEqual(len(at.exception),0)
        self.assertFalse(at.get('component_instance'))
        at.text_input(key='login_username').set_value(username)
        at.text_input(key='login_password').set_value(password)
        at.button[0].click().run()
        self.assertEqual(len(at.exception),0)
        return at
    def test_viewer_has_no_management_or_downloads(self):
        at=self.signed_in('viewer_user','Test-only-viewer-password!123')
        self.assertFalse(any(t.label=='Manage users' for t in at.toggle))
        self.assertEqual(len(at.get('download_button')),0)
        self.assertEqual(len(at.get('file_uploader')),0)
        self.assertEqual(len(at.get('data_editor')),0)
    def test_admin_manage_users_and_revocation(self):
        at=self.signed_in('admin_user','Test-only-admin-password!123')
        at.toggle(key='workspace_users').set_value(True).run()
        self.assertEqual(len(at.exception),0)
        self.assertTrue(any(t.label=='New viewer username' for t in at.text_input))
        self.store.bootstrap_admin('admin_user','Rotated-password!123')
        at.run()
        self.assertTrue(any(t.label=='Username' for t in at.text_input))

    def test_three_tabs_share_clean_result_tables(self):
        import json
        from unittest.mock import Mock
        at=self.signed_in('viewer_user','Test-only-viewer-password!123')
        response=Mock(status_code=200,content=b'fixture',links={})
        response.json.return_value={"meta":{"results":{"total":45}},"results":[{
            "k_number":f"K240{i:03}","device_name":"Laser system", "applicant":"Example manufacturer",
            "decision_date":"20240101","openfda":{"device_class":["2"]}} for i in range(45)]}
        with patch('requests.Session.get',return_value=response):
            next(b for b in at.button if b.label=='Run search').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual([t.label for t in at.tabs],['FDA 510(k)','CDSCO Risk Classification','Approved Devices','Ask AI'])
        grids=at.get('component_instance')
        self.assertEqual(len(grids),3)
        args=[json.loads(g.proto.json_args) for g in grids]
        self.assertEqual(len(args[0]['rows']),45)
        self.assertTrue(all('20 results per page' in g['description'] for g in args))
        self.assertEqual(len(at.get('download_button')),0)
        self.assertFalse(any('Filter Controls' in e.label for e in at.expander))
        self.assertEqual(sum(e.label=='Source details' for e in at.expander),3)

    def test_ask_ai_uses_current_results_and_renders_query_evidence(self):
        from unittest.mock import Mock
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test-private-key'}):
            at=self.signed_in('viewer_user','Test-only-viewer-password!123')
            response=Mock(status_code=200,content=b'fixture',links={})
            response.json.return_value={"meta":{"results":{"total":2}},"results":[{"k_number":"K240001","device_name":"Laser","applicant":"Example","decision_date":"20240101"},{"k_number":"K240002","device_name":"Laser","applicant":"Example","decision_date":"20240102"}]}
            with patch('requests.Session.get',return_value=response):
                next(b for b in at.button if b.label=='Run search').click().run()
            assert not at.exception
            question=at.text_area(key='research_ai_question')
            question.set_value('How many loaded FDA records?')
            with patch('grounded_ai.generate') as blocked:
                next(b for b in at.button if b.label=='Ask AI').click().run()
                blocked.assert_not_called()
            assert any('Tick the sharing checkbox' in e.value for e in at.error)
            at.checkbox(key='research_ai_consent').set_value(True)
            with patch('grounded_ai.generate',side_effect=[{'queries':[{'table':'T1','metrics':[{'column':'*','op':'count'}]}],'clarification':''},'There are 2 loaded FDA records [T1:R1, T1:R2] [Q1].']) as generate:
                next(b for b in at.button if b.label=='Ask AI').click().run()
                assert at.checkbox(key='research_ai_consent').value is True
                assert not at.exception
                assert generate.call_count==2
                assert generate.call_args.args[3]['evidence'][0]['records']==[{'count(*)':2}]
            assert any(m.value=='There are 2 loaded FDA records.' for m in at.markdown)
            assert at.text_area(key='research_ai_question').value==''
            at.run()
            assert at.checkbox(key='research_ai_consent').value is True
            assert any('[Q1]' in e.label for e in at.expander)
            at.text_area(key='research_ai_question').set_value('Extract intended use from the K240001 summary PDF.')
            document={'name':'K240001 FDA summary','k_number':'K240001','url':'https://www.accessdata.fda.gov/cdrh_docs/pdf24/K240001.pdf','status':'read','sha256':'a'*64,'total_pages':1,'read_pages':1,'warnings':[],'pages':[{'page':1,'text':'Intended use: soft tissue cutting. Bench testing: optical output.'}]}
            plan={'queries':[{'table':'T1','filters':[{'column':'510(k) Number','op':'eq','value':'K240001'}]}],'read_fda_pdfs':True}
            with patch('fda_pdf.fetch_fda_summary',return_value=document) as fetch,patch('grounded_ai.generate',side_effect=[plan,'The summary describes soft tissue cutting.']):
                next(b for b in at.button if b.label=='Ask AI').click().run()
                assert not at.exception
                fetch.assert_called_once_with('K240001')
            assert any(e.label.startswith('PDF source: K240001') for e in at.expander)
            assert any(s.label=='Review extracted page' for s in at.selectbox)
            assert any('Intended use: soft tissue cutting' in t.value for t in at.text)
            assert at.text_area(key='research_ai_question').value==''
            at.text_area(key='research_ai_question').set_value('Extract intended use from the K240001 summary PDF.')
            with patch('fda_pdf.fetch_fda_summary',return_value=document),patch('grounded_ai.generate',side_effect=[plan,'The summary describes soft tissue cutting.']):
                next(b for b in at.button if b.label=='Ask AI').click().run()
                assert not at.exception
            assert sum(e.label.startswith('PDF source: K240001') for e in at.expander)==2

            at.text_area(key='research_ai_question').set_value('Keep this question if the provider fails.')
            with patch('grounded_ai.generate',side_effect=ValueError('Quota reached')):
                next(b for b in at.button if b.label=='Ask AI').click().run()
                assert not at.exception
                assert at.text_area(key='research_ai_question').value=='Keep this question if the provider fails.'
            next(b for b in at.button if b.label=='Clear chat').click().run()
            assert not at.session_state['_research_ai_messages']

if __name__=='__main__':unittest.main()
