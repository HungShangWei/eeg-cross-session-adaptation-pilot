"""One concrete numerical dependency set for both wrappers. No computations at import."""
import numpy as np
from accounting import array_identity
from contracts import ValidityStop
class NumericDependencies:
 def __init__(self,account):self.account=account
 def guard(self):self.account.lease()
 def identity(self,x):return array_identity(x)
 def take(self,x,positions):return np.asarray(x)[list(positions)]
 def forward(self,model,x,fn):
  from neural_recipe import state_hash
  return self.account.run('forward',{'model_sha256':state_hash(model),'input':array_identity(x)},fn)
 def features(self,model,x):
  from neural_recipe import features
  return features(model,x,self)
 def update_n(self,model,moments,x,k):
  from neural_recipe import update_n
  return update_n(model,moments,x,self,k=k)
 def head_logits(self,f,W,b):
  from neural_recipe import head_logits
  return head_logits(f,W,b)
 def neural_gap(self,f,W,b):
  z=self.head_logits(f,W,b);return z[:,1]-z[:,0]
 def ea_gap(self,h,coef):return h@coef[:-1]+coef[-1]
 def prefix_whitening(self,x,ws):
  from ea_recipe import prefix_whitening
  return prefix_whitening(x,ws,self.account)
 def ea_transform(self,ea,x,W=None):
  from array_edges import ea_transform
  return ea_transform(ea,x,W)
 def _fit(self,kind,fn,args,kwargs):
  identity={'args':[array_identity(a) if hasattr(a,'shape') or isinstance(a,(list,tuple)) else a for a in args],
   'kwargs':{k:array_identity(v) if hasattr(v,'shape') or isinstance(v,(list,tuple)) else v for k,v in kwargs.items()}}
  from solvers_recipe import eligible
  skip=(kind in ('T_grid','H_optimizer') and not eligible(args[1])) or (kind=='EA_optimizer' and kwargs.get('source') is not None and not eligible(kwargs['yt']))
  if skip:return self.account.skipped(kind,identity,lambda:fn(*args,**kwargs))
  return self.account.run(kind,identity,lambda:fn(*args,**kwargs))
 def temperature(self,*a,**kw):
  from solvers_recipe import temperature
  return self._fit('T_grid',temperature,a,kw)
 def fit_head(self,*a,**kw):
  from solvers_recipe import fit_head
  return self._fit('H_optimizer',fit_head,a,kw)
 def logistic(self,*a,**kw):
  from solvers_recipe import logistic
  return self._fit('EA_optimizer',logistic,a,kw)
 def prediction_payload(self,q,ids,gap):
  byid=dict(zip(ids,gap))
  if len(byid)!=len(ids):raise ValidityStop('PREDICTION_DUPLICATE_ID')
  values=tuple(float(byid[i]) if i in byid and np.isfinite(byid[i]) else None for i in q)
  return {'ordinals':tuple(q),'gap':values,'valid':tuple(v is not None for v in values)}
