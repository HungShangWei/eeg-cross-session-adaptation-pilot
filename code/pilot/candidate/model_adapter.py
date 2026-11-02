"""TH-only numerical adapter. No scientific import until constructed by approved entry."""
import copy,json,pathlib,hashlib
from audit_core import BoundaryError,digest
from content_identity import content_identity,state_identity,Store
from account import Account
class ModelAdapter:
    def __init__(self,audit,code_identity,config):
        from numeric_dependencies import NumericDependencies
        self.audit=audit;self.code_identity=code_identity;self.config=config
        self.account=Account(audit);self.deps=NumericDependencies(self.account);self.store=Store(audit);self.normalization={}
    def view_identity(self,view):
        return {'requested':list(view.requested),'ordinals':list(view.neural.ordinals),
            'valid':list(view.epoch_mask.values),'feature_identity':content_identity(view.neural.values),
            'label_ordinals':list(view.labels.ordinals),'label_value_identity':content_identity(view.labels.values)}
    def prepare_source(self,person,service):
        decision=self.config['source_plan'][str(person)]
        if decision['preprocessing']!='REBUILD_REQUIRED' or decision['seeds']!={str(s):'REBUILD_REQUIRED' for s in (1103,2207,3301)}:
            raise BoundaryError('UNIMPLEMENTED_OR_UNAPPROVED_SOURCE_BRANCH')
        return self.build_source(person,service)
    def build_source(self,person,service):
        from contracts import StagedSourceBroker,validate_development
        from source_recipe_e3prep import prepare_full_source
        from types import SimpleNamespace
        blocks=service.development(person);validate_development(blocks,service.n_source(person))
        identity=service.source_input_identity(person)
        def sink(event):
            result=self.store.record(event['event'],event)
            if event['event']=='source_choices_frozen':service.freeze_source(person,event['freeze_sha256'],event['payload'])
            return result
        broker=StagedSourceBroker(blocks,lambda:service.scal(person),service.n_source(person),identity,sink)
        development=broker.development('B2R-source-only')
        binding={'status':'DEVELOPMENT_BOUND','participant':person,'broker_identity':broker.identity}
        permit=SimpleNamespace(scope='B2R',code_sha256=self.code_identity)
        with self.account.stage_scope('source-training-and-development',participant=person,
                    development_content={k:self.view_identity(v) for k,v in blocks.items()},
                    preprocessing_identity=service.normalization_identity(person)):
            raw=prepare_full_source(person,broker,self.account,self.store.record,permit,self.code_identity,development,binding)
        self.normalization[person]=service.normalization_identity(person)
        result={}
        for s in raw['neural_sources']:
            state={'kind':'neural','person':person,'model':s['model'],'moments':s['moments'],
                'W':s['source_W'].copy(),'b':s['source_b'].copy(),'Ts':s['Ts'],'choices':raw['choices'],
                'source_state_sha256':s['source_state_sha256'],'status':s['calibration_status']}
            self.store.record('source_snapshot_frozen',{'participant':person,'seed':s['base'],'freeze':raw['freeze_sha256'],
                'model_state':state['model'].state_dict(),'state':{k:v for k,v in state.items() if k!='model'},
                'normalization_identity':self.normalization[person]})
            result[s['base']]=state
        if set(result)!={1103,2207,3301}:raise BoundaryError('THREE_SOURCE_SEEDS')
        return result
    def clone_source(self,state):return copy.deepcopy(state)
    def state_identity(self,state,person):return state_identity(state,self.normalization[person])
    def adapt(self,state,method,view,feedback,request):
        from composition import adapt_core
        self.account.target_feedback=(feedback,request['recipient'],request['call_id'],digest(content_identity(view.labels.values)))
        self.account._labels=view.labels.values
        try:
            with self.account.stage_scope('target-adaptation',recipient=request['recipient'],call_id=request['call_id']):
                result,events=adapt_core(state,method,10,view,self.deps)
            # Legacy returned events are not used to fabricate the live audit ledger.
            return result
        finally:self.account.target_feedback=None;self.account._labels=None
    def store_state(self,ref,state,before,after,request):
        return self.store.record('adapted_state_saved',{'ref':ref,'prefix_call_id':request['call_id'],
            'before':before,'after':after,'model_state':state['model'].state_dict(),
            'state':{k:v for k,v in state.items() if k!='model'}})
    def predict(self,ref,state,q):
        from composition import predict_core
        with self.account.stage_scope('target-Q-prediction',recipient=ref):payload=predict_core(state,q.requested,q,self.deps)
        return {'ref':ref,'ordinals':list(payload['ordinals']),'gap':list(payload['gap']),
                'valid':list(payload['valid']),'temperature':float(state['Ts'])}
    def score_sealed(self,cohort,labels,token):
        import numpy as np
        from scorer import score,aggregate,original_primary_inference
        from statistics_recipe import score_synthetic
        path=pathlib.Path(self.config['bootstrap']['path']);expected=self.config['bootstrap']
        if path.stat().st_size!=expected['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:raise BoundaryError('EXISTING_BOOTSTRAP_IDENTITY')
        indices=np.load(path,allow_pickle=False)
        if indices.shape!=(10000,9) or indices.dtype!=np.dtype('int64') or np.any((indices<0)|(indices>8)):raise BoundaryError('BOOTSTRAP_SCHEMA')
        rows=[];fits={'T':[[False]*3 for _ in range(9)],'H':[[False]*3 for _ in range(9)]}
        for ref,row in sorted(cohort.rows.items()):
            p,s,m,_=ref.split(':');p=int(p);s=int(s)
            payload=json.loads(pathlib.Path(row['prediction_file']['path']).read_text())
            result=score(payload,labels[p],cohort.expected_q[p])
            # Independent original arithmetic check on the same new saved outputs.
            old=score_synthetic([float('nan') if x is None else x for x in payload['gap']],labels[p]['values'],payload['valid'],T=payload['temperature'],cost=.25,sealed=True)
            for k in ('accepted','accepted_wrong','deferred','technical_deferred','denominator'):
                if result[k]!=old[k]:raise BoundaryError('EXACT_COUNT_VERIFICATION')
            for k in ('J','C'):
                if abs(result[k]-old[k])>1e-12:raise BoundaryError('FIXED_METRIC_TOLERANCE')
            rows.append(dict(participant=p,seed=s,method=m,**result))
            st=row['fit_status'];fits[m][p-1][(1103,2207,3301).index(s)]=bool(st.get('active') and not st.get('fallback') and st.get('status')=='completed')
        summary=aggregate(rows);inference=original_primary_inference(summary['participants'],fits['T'],fits['H'],indices)
        from independent_statistics import independent_primary,compare_primary
        independent=independent_primary(summary['participants'],fits['T'],fits['H'],indices)
        compare_primary(inference,independent,absolute_tolerance=self.config['tolerances']['bounds_absolute'])
        output={'run_id':self.audit.run_id,'seal':token,'instance_metrics':rows,'summary':summary,'primary':inference,
             'independent_primary_check':independent,'old_DREC_values_compared':False,'new_execution_not_fresh_blind':True}
        self.audit.store_json('scoring/primary_results.json',output)
        self.audit.event('scoring_complete',seal_sha256=token,instances=54,independent_n=9)
        return output
