"""Content identities and transparent storage, called only after explicit run grant.
No pickle, no project imports at module import time.
"""
import hashlib,json,pathlib,os
from audit_core import digest,checked,BoundaryError
def content_identity(x):
    if hasattr(x,'detach'):x=x.detach().cpu().numpy()
    if hasattr(x,'dtype') and hasattr(x,'shape'):
        import numpy as np
        a=np.asarray(x)
        if a.dtype.hasobject:raise BoundaryError('OBJECT_ARRAY')
        return {'dtype':str(a.dtype),'shape':list(a.shape),'sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest()}
    if isinstance(x,dict):return {str(k):content_identity(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [content_identity(v) for v in x]
    if hasattr(x,'item'):return x.item()
    if x is None or type(x) in (int,float,str,bool):return x
    raise BoundaryError('UNKNOWN_STATE_TYPE')
def state_identity(state,normalization_identity):
    return {'encoder_and_bn_and_embedded_source_head':digest(content_identity(state['model'].state_dict())),
        'normalization':normalization_identity,'moments':digest(content_identity(state['moments'])),
        'head_W':digest(content_identity(state['W'])),'head_b':digest(content_identity(state['b'])),
        'temperature':float(state['Ts']),'choices':digest(state['choices']),
        'source_state_sha256':state['source_state_sha256'],'status':state.get('status'),
        'person':state['person'],'kind':state['kind']}
class Store:
    def __init__(self,audit):self.audit=audit;self.sequence=0
    def record(self,event,payload):
        import numpy as np
        self.sequence+=1;arrays={}
        def encode(x):
            if hasattr(x,'detach'):x=x.detach().cpu().numpy()
            if hasattr(x,'dtype') and hasattr(x,'shape'):
                a=np.asarray(x)
                if a.dtype.hasobject or a.nbytes>33554432:raise BoundaryError('ARRAY_BOUND')
                key=f'a{len(arrays):04d}';arrays[key]=a
                return {'array':key,**content_identity(a)}
            if isinstance(x,dict):return {str(k):encode(v) for k,v in x.items()}
            if isinstance(x,(tuple,list)):return [encode(v) for v in x]
            if hasattr(x,'item'):return x.item()
            if x is None or type(x) in (int,float,str,bool):return x
            raise BoundaryError('UNSUPPORTED_STORAGE')
        encoded=encode(payload);base=f'artifacts/{self.sequence:06d}-{event}'
        if sum(a.nbytes for a in arrays.values())>4*1048576:raise BoundaryError('ARTIFACT_AGGREGATE_BOUND')
        if arrays:
            p=checked(self.audit.root,self.audit.root/(base+'.npz'));p.parent.mkdir(parents=True,exist_ok=True)
            self.audit.guard()
            with p.open('xb') as f:np.savez(f,**arrays);f.flush();os.fsync(f.fileno())
            archive={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
        else:archive=None
        record=self.audit.store_json(base+'.json',{'event':event,'payload':encoded,'archive':archive})
        event_id=self.audit.event(event,artifact=record,payload_identity=digest(encoded),archive=archive)
        return {'event_id':event_id,'record':record,'payload_identity':digest(encoded)}
