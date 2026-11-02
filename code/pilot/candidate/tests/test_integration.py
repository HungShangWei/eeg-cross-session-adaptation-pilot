"""SYNTHETIC ONLY. Calls actual candidate boundaries with numerical/model doubles.
No real model construction/fit/forward, MAT body, target values or old predictions.
"""
import unittest,pathlib,sys,tempfile,copy,json,types,math,hashlib
from unittest.mock import patch
C=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(C/'runtime_modules'),str(C/'frozen'),str(C)]
import numpy as np
from audit_core import Audit,Feedback,Cohort,BoundaryError,read_events,state_change
from contracts import Block,Indexed
from flow import execute_core
from data_service import DataService
from model_adapter import ModelAdapter
from content_identity import content_identity
from account import Account
from numeric_dependencies import NumericDependencies
from scorer import original_primary_inference
from independent_statistics import independent_primary,compare_primary,bounds
CONFIG=json.loads((C/'config/RUN_CONFIG_v1.json').read_text())
def view(q,labels=True):
    q=tuple(q);x=np.zeros((len(q),3,512),dtype=np.float32)
    return Block(q,Indexed(q,x),Indexed(q,x.astype(np.float64)),Indexed(q,tuple(True for _ in q)),
                 Indexed(q if labels else (),tuple(i%2 for i in q) if labels else ()))
class FakeService:
    def __init__(self,audit):self.audit=audit;self.qualified={};self.released=False
    def qualify(self,p):self.qualified[p]=self.audit.event('SYNTHETIC_qualification',participant=p)
    def target_container_hashes(self):return {p:str(p)*64 for p in range(1,10)}
    def expected_q(self):return {p:[40,41] for p in range(1,10)}
    def view_identity(self,v):return DataService.view_identity(self,v)
    def prefix(self,r):return dict(r,valid=[True]*10,label_ordinals=list(range(10)),sample_onset_indices=list(range(100,110))),view(range(10))
    def q_features(self,p):return view([40,41],False)
    def scoring_labels(self,token):
        self.released=True;return DataService.scoring_labels(self,token)
    @property
    def cache(self):
        # Only synthetic label values and a split double; no MAT or real data.
        return {p:{'split':types.SimpleNamespace(part=lambda k:(40,41)), 'target':(None,None,[1]*40+[2,1])} for p in range(1,10)}
class FakeAdapter:
    def __init__(self,audit,fail=False,fallback=True):self.audit=audit;self.config=CONFIG;self.fail=fail;self.fallback=fallback
    def prepare_source(self,p,service):
        if set(service.qualified)!=set(range(1,10)):raise AssertionError('fit before nine')
        self.audit.event('SYNTHETIC_source_ready',participant=p)
        return {s:{'encoder':'fixed','normalization':'fixed','head_W':'fixed','head_b':'fixed','temperature':1.,'status':{'status':'source','active':False}} for s in (1103,2207,3301)}
    def clone_source(self,s):return copy.deepcopy(s)
    def state_identity(self,s,p):return copy.deepcopy(s)
    def view_identity(self,v):return DataService.view_identity(self,v)
    def adapt(self,s,m,v,feedback,r):
        feedback.use(r['recipient'],r['call_id'],'schema_validation',content_identity(v.labels.values))
        if self.fail:raise RuntimeError('SYNTHETIC_ABORT')
        feedback.use(r['recipient'],r['call_id'],'class_gate',content_identity(v.labels.values))
        fallback=self.fallback and r['recipient']=='1:1103:T:10'
        if not fallback:feedback.use(r['recipient'],r['call_id'],'optimizer',content_identity(v.labels.values))
        s['status']={'status':'prefix_labels_insufficient' if fallback else 'completed','active':not fallback,'fallback':fallback};return s
    def store_state(self,ref,s,before,after,r):
        record=self.audit.store_json('states/'+ref+'.json',{'payload':s,'archive':None})
        return {'event_id':self.audit.event('SYNTHETIC_state_persisted',ref=ref,before=before,after=after,record=record),'record':record}
    def predict(self,ref,s,q):return {'ref':ref,'ordinals':[40,41],'valid':[True,True],'gap':[2.,-2.],'temperature':1.}
    def score_sealed(self,c,l,t):return ModelAdapter.score_sealed(self,c,l,t)
class Integration(unittest.TestCase):
    def setUp(self):
        self.root=pathlib.Path(tempfile.mkdtemp(prefix='synthetic-integration-',dir=C.parent/'tmp'));self.a=Audit(self.root,'SYNTHETIC_INTEGRATION','FIXTURE')
    def tearDown(self):self.a.close()
    def test_full_real_flow_with_54_synthetic_instances_and_fallback(self):
        s=FakeService(self.a);out=execute_core(s,FakeAdapter(self.a),self.a,'SYNTHETIC_CODE')
        self.assertTrue(s.released);self.assertEqual(len(out['instance_metrics']),54);self.assertEqual(out['summary']['n'],9)
        self.assertEqual(out['summary']['group']['T_J'],0.);self.assertEqual(out['summary']['group']['T_C'],1.)
        rows=read_events(self.a.path);names=[r['event'] for r in rows]
        self.assertEqual(names.count('labels_received'),54);self.assertEqual(names.count('label_access_ended'),54)
        first_fit=names.index('SYNTHETIC_source_ready');self.assertEqual(names[:first_fit].count('SYNTHETIC_qualification'),9)
        self.assertLess(names.index('all_predictions_sealed'),names.index('Q_labels_release_enter'))
        seals=json.loads((self.root/'seal.json').read_text());self.assertEqual(sum(r['outcome']=='protocol_fallback' for r in seals['rows']),1)
        # Service itself rechecks the stored seal fingerprint before returning labels.
        with self.assertRaises(BoundaryError):s.scoring_labels('wrong')
        prediction=pathlib.Path(seals['rows'][0]['prediction_file']['path']);prediction.write_text('{}')
        with self.assertRaises(BoundaryError):s.scoring_labels(out['seal'])
    def test_sealed_state_change_and_duplicate_rejected(self):
        s=FakeService(self.a);out=execute_core(s,FakeAdapter(self.a),self.a,'SYNTHETIC_CODE');seal=json.loads((self.root/'seal.json').read_text())
        c=Cohort(self.a,s.expected_q(),'SYNTHETIC_CODE');row=seal['rows'][0];c.add(row)
        with self.assertRaisesRegex(BoundaryError,'COHORT_DUPLICATE'):c.add(row)
        path=pathlib.Path(row['state_artifact']['record']['path']);path.write_text('{}')
        with self.assertRaisesRegex(BoundaryError,'STATE_RECORD_CHANGED'):s.scoring_labels(out['seal'])
    def test_acceptance_threshold_exact_counts(self):
        from scorer import score
        from statistics_recipe import score_synthetic
        t=float(np.log(3.));g=[float(np.nextafter(t,-np.inf)),t,float(np.nextafter(t,np.inf))]
        saved={'ordinals':[40,41,42],'gap':g,'valid':[True]*3,'temperature':1.};labels={'ordinals':[40,41,42],'values':[1,0,1]}
        a=score(saved,labels,saved['ordinals']);b=score_synthetic(g,labels['values'],saved['valid'],sealed=True)
        for key in ('accepted','accepted_wrong','deferred','denominator'):self.assertEqual(a[key],b[key])
    def test_actual_flow_abort_never_seals_or_releases_labels(self):
        s=FakeService(self.a)
        with self.assertRaisesRegex(RuntimeError,'SYNTHETIC_ABORT'):execute_core(s,FakeAdapter(self.a,fail=True),self.a,'SYNTHETIC_CODE')
        self.assertFalse(s.released);self.assertFalse((self.root/'seal.json').exists())
        end=[r for r in read_events(self.a.path) if r['event']=='label_access_ended'];self.assertEqual(len(end),1);self.assertFalse(end[0]['successful_close'])
        outcome=json.loads((self.root/'operation_outcomes_incomplete.json').read_text());self.assertEqual(len(outcome),54)
    def test_actual_adapter_fit_receipts_with_solver_and_forward_doubles(self):
        import solvers_recipe
        class Model:
            def state_dict(self):return {'synthetic_fixed':np.array([1.],dtype=np.float32)}
        for method in ('T','H'):
            adapter=object.__new__(ModelAdapter);adapter.audit=self.a;adapter.account=Account(self.a);adapter.deps=NumericDependencies(adapter.account)
            adapter.deps.features=lambda model,x:np.zeros((len(x),3),dtype=np.float64)
            state={'person':1,'kind':'neural','model':Model(),'moments':(), 'W':np.zeros((2,3)), 'b':np.zeros(2),'Ts':1.,'choices':{'T':{'selected':[2,.1]},'H':{'selected':[.1]}},'status':{'status':'source','active':False},'source_state_sha256':'synthetic'}
            f=Feedback(self.a,{p:str(p)*64 for p in range(1,10)});r=f.request(1,1103,method);v=view(range(10));reply=dict(r,valid=[True]*10,label_ordinals=list(range(10)),sample_onset_indices=list(range(100,110)));f.receive(r,reply,DataService.view_identity(None,v))
            with patch.object(solvers_recipe,'temperature',return_value=(1.2,{'status':'completed','active':True,'fallback':False})),patch.object(solvers_recipe,'fit_head',return_value=(np.ones((2,3)),np.ones(2),{'status':'completed','active':True,'fallback':False})):
                result=adapter.adapt(state,method,v,f,r)
            f.end(r['recipient'],r['call_id'],'completed');self.assertEqual(result['status']['status'],'completed')
        purposes=[r['purpose'] for r in read_events(self.a.path) if r['event']=='labels_used']
        self.assertEqual(purposes.count('schema_validation'),2);self.assertEqual(purposes.count('class_gate'),2);self.assertEqual(purposes.count('optimizer'),2)
    def test_original_intervals_and_existing_matrix_wiring_synthetic_only(self):
        from statistics_recipe import bounds as original_bounds,hp1_label,robustness
        expected={'mean':5.,'sd':math.sqrt(7.5)};b=bounds(range(1,10));self.assertAlmostEqual(b['mean'],expected['mean']);self.assertAlmostEqual(b['upper'],5+2.306004135204166*expected['sd']/3,places=12)
        for k in ('mean','lower','upper'):self.assertLessEqual(abs(b[k]-original_bounds(range(1,10))[k]),1e-10)
        raw=pathlib.Path(CONFIG['bootstrap']['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),CONFIG['bootstrap']['sha256'])
        indices=np.load(pathlib.Path(CONFIG['bootstrap']['path']),allow_pickle=False)
        people=[{'participant':p,'T_J':p/100,'H_J':p/100+.01,'T_C':.8-p/100,'H_C':.65} for p in range(1,10)];fits=[[True]*3 for _ in people]
        self.assertTrue(compare_primary(original_primary_inference(people,fits,fits,indices),independent_primary(people,fits,fits,indices)))
        self.assertTrue(hp1_label('ESTABLISHED',True,False,True).startswith('HP1_SUPPORTED'))
        self.assertEqual(robustness(False,[True,True,True]),'no_bootstrap_upgrade')
    def test_formal_entry_rejects_prep_policy_in_fixture_namespace(self):
        import launch,supervise
        c=self.root/'fixture_candidate';(c/'config').mkdir(parents=True);conf=dict(CONFIG,preparation_status='READY_FOR_EXECUTION_APPROVAL',run_root=str(self.root/'NEVER_CREATED'))
        (c/'config/RUN_CONFIG_v1.json').write_text(json.dumps(conf));grant=self.root/'SYNTHETIC_GRANT.json';grant.write_text(json.dumps({'resource_policy':'PREP_WARN_ALLOWED'}))
        for module in (launch,supervise):
            with patch.object(module,'C',c),patch.object(module,'identity_check',return_value='SYNTHETIC'),patch.object(sys,'argv',['fixture','--identity','SYNTHETIC','--approval',str(grant),'--run-root',conf['run_root']]):
                with self.assertRaisesRegex(PermissionError,'FORMAL_REJECTS_PREP_POLICY'):module.main()
        self.assertFalse(pathlib.Path(conf['run_root']).exists());self.assertFalse(pathlib.Path(CONFIG['run_root']).exists())
    def test_formal_guard_warn_is_still_rejected(self):
        import resource_guard
        fake_vm='Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 2000000.\nPages inactive: 0.\nPages speculative: 0.\nSwapouts: 1.\n'
        def native(owner,argv):
            if 'vm_stat' in argv[0]:return fake_vm,1
            if 'sysctl' in argv[0]:return '2\n',1
            return '',1
        with patch.object(resource_guard,'native_call',side_effect=native):
            with self.assertRaisesRegex(BoundaryError,'FORMAL_RAM_OR_PRESSURE'):resource_guard.ResourceGuard(self.a,CONFIG).check(initial=True)
    def test_environment_and_complete_identity_are_enforced(self):
        import launch,importlib.metadata
        launch.environment_check()
        with patch.object(importlib.metadata,'version',return_value='SYNTHETIC_WRONG_VERSION'):
            with self.assertRaisesRegex(PermissionError,'PACKAGE_VERSION_CHANGED'):launch.environment_check()
        identity=self.root/'incomplete_identity.json';identity.write_text('{"files":[]}')
        with self.assertRaisesRegex(PermissionError,'INCOMPLETE_CANDIDATE_IDENTITY'):launch.identity_check(identity)
    def test_service_source_gates_use_actual_methods_without_data(self):
        from audit_core import digest
        service=object.__new__(DataService);service.audit=self.a;service.qualified={};service.developed=set();service.scal_released=set();service.frozen={}
        with self.assertRaisesRegex(BoundaryError,'ALL_NINE'):service.development(1)
        with self.assertRaisesRegex(BoundaryError,'SCAL_AFTER_FREEZE'):service.scal(1)
        service.developed={1};service.source_input_identity=lambda p:{'participant':p,'partition':'source-only-development'};service.normalization_identity=lambda p:'SYNTHETIC_PREPROCESSOR'
        payload={'input_identity':service.source_input_identity(1),'choices':{'T':{},'H':{},'checkpoint':{}},'state_hashes':{'1103':'a','2207':'b','3301':'c'}}
        service.freeze_source(1,digest(payload),payload)
        service.cache={1:{'split':types.SimpleNamespace(part=lambda key:tuple(range(140,160)))}}
        service._block=lambda p,which,ids,allowed:('SYNTHETIC_SCAL',tuple(ids))
        self.assertEqual(service.scal(1)[1],tuple(range(140,160)))
        with self.assertRaisesRegex(BoundaryError,'SCAL_AFTER_FREEZE'):service.scal(1)
    def test_actual_content_identity_detects_model_and_normalization_change(self):
        from content_identity import state_identity
        class Model:
            def __init__(self):self.buffer=np.zeros(2,dtype=np.float32)
            def state_dict(self):return {'bn.running_mean':self.buffer}
        s={'model':Model(),'moments':(),'W':np.zeros((2,3)),'b':np.zeros(2),'Ts':1.,'choices':{},'source_state_sha256':'SYNTHETIC','person':1,'kind':'neural','status':None}
        before=state_identity(s,'fixed');s['model'].buffer[0]=1
        with self.assertRaisesRegex(BoundaryError,'FORBIDDEN_STATE_CHANGE'):state_change('H',before,state_identity(s,'fixed'))
        s['model'].buffer[0]=0
        with self.assertRaisesRegex(BoundaryError,'FORBIDDEN_STATE_CHANGE'):state_change('T',before,state_identity(s,'changed'))
    def test_source_post_transform_join_preserves_valid_subset_without_refill(self):
        import trusted_ingress
        def service_and_blocks(wrong=False):
            service=object.__new__(DataService);service.audit=self.a;service.qualified={p:'SYNTHETIC' for p in range(1,10)};service.developed=set()
            raw={'raw':Indexed((0,1,2),(0,0,0)),'labels':Indexed((0,1,2),(0,1,0)),'precue':Indexed((0,1,2),(0,0,0))}
            service.cache={1:{'raw_development':{'S-fit':raw,'D2':raw},'target':(None,[0,1,2],None),'qualification_content':'SYNTHETIC_RAW_IDENTITY'}}
            service.source_input_identity=lambda p:{'source':'SYNTHETIC'};service.n_source=lambda p:160;service.store=types.SimpleNamespace(record=lambda *a:None)
            pipe=types.SimpleNamespace(B=np.zeros((3,3)),mean=np.zeros(3),std=np.ones(3),floor=np.zeros(3,dtype=bool),nuisance={})
            fit=view((0,2))
            if wrong:fit=Block(fit.requested,fit.neural,fit.corrected_uV,fit.epoch_mask,Indexed((0,2),(1,1)))
            return service,pipe,{'S-fit':fit,'D2':view((0,2))}
        s,pipe,blocks=service_and_blocks()
        with patch.object(trusted_ingress,'preprocess_development',return_value=(pipe,blocks,{})):
            self.assertEqual(s.development(1)['S-fit'].neural.ordinals,(0,2))
        s,pipe,blocks=service_and_blocks(True)
        with patch.object(trusted_ingress,'preprocess_development',return_value=(pipe,blocks,{})):
            with self.assertRaisesRegex(BoundaryError,'QUALIFICATION_CHANGED'):s.development(1)
if __name__=='__main__':unittest.main(verbosity=2)
