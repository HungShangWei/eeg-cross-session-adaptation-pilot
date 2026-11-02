"""New-run actual call boundaries only. Does not read or debit old journals."""
import contextlib,copy
from audit_core import digest,BoundaryError
from content_identity import content_identity
class Account:
    def __init__(self,audit):
        self.audit=audit;self.context={};self.target_feedback=None;self.counter=0;self.used={}
        self.caps={'optimizer_step':8100,'forward':30000,'T_grid':189,'H_optimizer':108,'model_create':27}
    def lease(self):self.audit.guard()
    def inspect_labels(self,purpose,labels):
        if self.target_feedback is None:return
        ledger,recipient,call_id,expected=self.target_feedback
        got=digest(content_identity(labels))
        if got!=expected:raise BoundaryError('LABEL_INPUT_NOT_RECEIPTED_VIEW')
        ledger.use(recipient,call_id,purpose,content_identity(labels))
    def run(self,kind,identity,fn):
        self.lease();self.counter+=1;self.used[kind]=self.used.get(kind,0)+1
        if kind not in self.caps or self.used[kind]>self.caps[kind]:raise BoundaryError('NEW_RUN_OPERATION_CAP')
        call=f'{self.audit.run_id}:primitive:{self.counter}'
        with self.audit.boundary('primitive',kind=kind,call_id=call,context=self.context,input_identity=content_identity(identity)) as out:
            result=fn();out['output_identity']=content_identity(result)
        return result
    def skipped(self,kind,identity,fn):
        self.lease()
        if self.target_feedback is not None:self.inspect_labels('solver_fallback_eligibility',self._labels)
        with self.audit.boundary('primitive_protocol_skip',kind=kind,context=self.context,input_identity=identity) as out:
            result=fn();out['output_identity']=content_identity(result)
        return result
    def new_model(self,person,seed,factory):
        self.used['model_create']=self.used.get('model_create',0)+1
        if self.used['model_create']>self.caps['model_create']:raise BoundaryError('MODEL_CREATE_CAP')
        with self.audit.boundary('model_create',participant=person,effective_seed=seed) as out:
            model=factory();out['output_identity']=content_identity(model.state_dict())
        return model
    def end_trajectory(self,participant,effective_seed,model_sha256):
        self.audit.event('source_trajectory_closed',context=self.context,participant=participant,effective_seed=effective_seed,model_sha256=model_sha256)
    @contextlib.contextmanager
    def stage_scope(self,stage,**context):
        old=self.context;self.context={'stage':stage,**context}
        try:yield
        finally:self.context=old
