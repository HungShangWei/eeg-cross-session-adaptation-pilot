"""Synthetic, hand-checkable engineering fixtures only.
No real model, signals, prefix/Q values, fitting or prediction generation.
"""
import sys,pathlib,tempfile,unittest,subprocess,copy,json,math
from unittest.mock import patch
C=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
from audit_core import Audit,Feedback,Cohort,BoundaryError,state_change,read_events
from scorer import score,aggregate
class Boundaries(unittest.TestCase):
    def setUp(self):
        self.root=pathlib.Path(tempfile.mkdtemp(prefix='synthetic-',dir=C.parent/'tmp'));self.a=Audit(self.root,'SYNTHETIC_ONLY','FIXTURE')
    def tearDown(self):self.a.close()
    def receipt(self):
        f=Feedback(self.a,{p:str(p)*64 for p in range(1,10)});r=f.request(1,1103,'T')
        reply=dict(r,valid=[True]*10,label_ordinals=list(range(10)),sample_onset_indices=list(range(100,110)))
        return f,r,reply
    def test_a_durable_feedback_after_process_exit(self):
        root=self.root/'child';root.mkdir()
        result=subprocess.run([sys.executable,'-B',str(C/'tests/fixture_child.py'),str(root)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        events=read_events(root/'events.jsonl')
        self.assertEqual([x['event'] for x in events],['prefix_request','labels_received','labels_used','label_access_ended'])
        self.assertTrue(events[-1]['successful_close'])
    def test_b_wrong_identity_rejected(self):
        for field,bad in [('container_sha256','bad'),('recipient','1:2207:T:10'),('call_id','wrong'),('label_ordinals',list(range(1,11)))]:
            f,r,reply=self.receipt();reply[field]=bad
            with self.assertRaises(BoundaryError):f.receive(r,reply,{'synthetic':True})
    def test_c_no_seal_no_labels(self):
        c=Cohort(self.a,{p:[40,41] for p in range(1,10)},'fixture-code')
        called=[]
        with self.assertRaises(BoundaryError):c.release_labels('not-sealed',lambda:called.append(True))
        self.assertEqual(called,[])
    def test_d_frozen_state(self):
        before={'encoder':'a','bn':'b','normalization':'c','temperature':1.,'head_W':'w','head_b':'b','status':None}
        for key in ('encoder','bn','normalization'):
            after=dict(before);after[key]='changed'
            with self.assertRaises(BoundaryError):state_change('T',before,after)
            with self.assertRaises(BoundaryError):state_change('H',before,after)
        self.assertEqual(state_change('T',before,dict(before,temperature=2.))['changed'],['temperature'])
        with self.assertRaises(BoundaryError):state_change('H',before,dict(before,temperature=2.))
    def test_e_denominator_order_valid_and_incomplete(self):
        base={'ordinals':[40,41],'gap':[2.,None],'valid':[True,False],'temperature':1.}
        lab={'ordinals':[40,41],'values':[1,0]}
        for change in [{'ordinals':[41,40]},{'valid':[True]},{'valid':[True,True]},{'gap':[2.]}]:
            with self.assertRaises(BoundaryError):score(dict(base,**change),lab,[40,41])
        with self.assertRaises(BoundaryError):aggregate([])
        c=Cohort(self.a,{p:[40,41] for p in range(1,10)},'fixture')
        with self.assertRaises(BoundaryError):c.finish()
    def test_f_abort_and_write_failure_fail_closed(self):
        with self.assertRaises(ValueError):
            with self.a.boundary('operation'):raise ValueError('synthetic abort')
        rows=read_events(self.a.path)
        self.assertEqual(rows[-1]['event'],'operation_abort');self.assertFalse(rows[-1]['completed'])
        with patch('audit_core.os.write',side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError):self.a.event('cannot_write')
        self.assertTrue(self.a.poisoned)
        with self.assertRaises(BoundaryError):self.a.event('must_not_succeed')
    def test_g_hand_score_and_participant_aggregation(self):
        q=list(range(40,48));r=score({'ordinals':q,'gap':[2.,-2.,0.,None,2.,-2.,0.,None],
            'valid':[True,True,True,False,True,True,True,False],'temperature':1.},
            {'ordinals':q,'values':[1,0,0,1,0,1,1,0]},q)
        self.assertEqual((r['J'],r['C'],r['accepted_wrong'],r['technical_deferred']),(.375,.5,2,2))
        rows=[]
        for p in range(1,10):
            for seed,offset in zip((1103,2207,3301),(-.02,0.,.02)):
                rows.extend([{'participant':p,'seed':seed,'method':'T','J':p/20+offset,'C':.6+offset},
                             {'participant':p,'seed':seed,'method':'H','J':.3,'C':.5}])
        group=aggregate(rows);self.assertEqual(group['n'],9)
        self.assertAlmostEqual(group['group']['T_J'],.25,places=12)
        self.assertAlmostEqual(group['group']['T_minus_H_J'],-.05,places=12)
        with self.assertRaises(BoundaryError):aggregate(rows+[rows[0]])
    def test_h_write_scope(self):
        with self.assertRaises(BoundaryError):self.a.store_json('../escape.json',{'synthetic':True})
    def test_i_unapproved_entry_denies_before_future_root(self):
        result=subprocess.run([sys.executable,'-B',str(C/'launch.py'),'--check-unapproved'],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('EXECUTION_NOT_APPROVED',result.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
