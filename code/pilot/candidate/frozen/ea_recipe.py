"""Frozen EA/OAS/tangent pipeline, float64. No target reference update."""
import warnings
import numpy as np
from sklearn.covariance import OAS
from pyriemann.utils.mean import mean_riemann
from accounting import array_identity
class EAError(ValueError):pass
def eigen(a,account):
 return account.run("native_eigen",array_identity(a),lambda:np.linalg.eigh(a))
def spectral(a,power,account,log=False):
 a=(np.asarray(a,dtype=np.float64)+np.asarray(a,dtype=np.float64).T)/2
 tr=float(np.trace(a))
 if not np.isfinite(a).all() or not np.isfinite(tr) or tr<=0:raise EAError("SPD_TRACE")
 e,u=eigen(a,account);floor=1e-8*tr/3;clipped=int((e<floor).sum());e=np.maximum(e,floor)
 vals=np.log(e) if log else e**power
 return (u*vals)@u.T,{"floor":floor,"clipped":clipped,"condition":float(e[-1]/e[0])}
def whitening(x,account):
 x=np.asarray(x,dtype=np.float64)
 if x.ndim!=3 or x.shape[1:]!=(3,512) or not len(x) or not np.isfinite(x).all():raise EAError("EPOCH_SHAPE")
 c=np.mean(x@x.transpose(0,2,1)/512,axis=0);trace=float(np.trace(c))
 if trace<=0 or not np.isfinite(trace):raise EAError("ALIGNMENT_TRACE")
 R=c+1e-6*trace/3*np.eye(3);W,status=spectral(R,-.5,account);return W,status
def prefix_whitening(x,Ws,account):
 if len(x)<4:return Ws.copy(),{"status":"alignment_prefix_insufficient","active":False}
 try:
  w,s=account.run("native_alignment",{"x":array_identity(x),"Ws":array_identity(Ws)},lambda:whitening(x,account));return w,dict(s,status="completed",active=True)
 except EAError as e:return Ws.copy(),{"status":"alignment_failed_fallback","active":False,"reason":str(e)}
def covariances(x,W,account):
 out=[];status=[]
 for row_index,a in enumerate(x):
  aligned=W@np.asarray(a,dtype=np.float64);aligned-=aligned.mean(axis=1,keepdims=True)
  if not np.isfinite(aligned).all() or np.sum(aligned*aligned)<=0:raise EAError("COMMON_STRUCTURAL_INVALIDITY")
  c=account.run("OAS_fit",{"epoch":array_identity(a),"batch":array_identity(x),"row_index":row_index,"W":array_identity(W)},lambda:OAS(assume_centered=True,store_precision=False).fit(aligned.T).covariance_)
  fixed,s=spectral(c,1,account);out.append(fixed);status.append(s)
 return np.stack(out),status
def sym_log_spd(a,account):
 # Unlike covariance regularization, the congruence logarithm does not introduce
 # an extra recipe floor. Its eigenvalues must be positive.
 e,u=eigen((a+a.T)/2,account)
 if not np.isfinite(e).all() or np.any(e<=0):raise EAError("LOG_SPD")
 return (u*np.log(e))@u.T
def inverse_root(a,account):
 e,u=eigen((a+a.T)/2,account)
 if not np.isfinite(e).all() or np.any(e<=0):raise EAError("REFERENCE_SPD")
 return (u*(e**-.5))@u.T
class EAFeatures:
 def __init__(self,account):self.account=account
 def fit(self,x):
  self.Ws,self.align_status=self.account.run("native_alignment",array_identity(x),lambda:whitening(x,self.account));cs,self.oas_status=covariances(x,self.Ws,self.account)
  with warnings.catch_warnings(record=True) as caught:
   warnings.simplefilter("always")
   self.Q=self.account.run("Riemannian_reference",array_identity(cs),lambda:mean_riemann(cs,tol=1e-9,maxiter=100,init=cs.mean(axis=0)))
  self.qi=inverse_root(self.Q,self.account)
  residual=np.linalg.norm(np.mean([sym_log_spd(self.qi@c@self.qi,self.account) for c in cs],axis=0),"fro")
  self.reference_status={"residual":float(residual),"tolerance":1e-9,"maxiter":100,"warnings":[str(w.message) for w in caught]}
  if not np.isfinite(residual) or residual>1e-9:raise EAError("RIEMANNIAN_MEAN_NONCONVERGENCE")
  h=self.tangent(cs);self.mean=h.mean(axis=0);std=h.std(axis=0);self.scale=np.maximum(std,1e-8);self.floor=(std<1e-8)
  self.source_features=(h-self.mean)/self.scale;return self
 def tangent(self,cs):
  rows=[]
  for c in cs:
   l=sym_log_spd(self.qi@c@self.qi,self.account)
   rows.append([l[0,0],np.sqrt(2)*l[0,1],np.sqrt(2)*l[0,2],l[1,1],np.sqrt(2)*l[1,2],l[2,2]])
  return np.asarray(rows,dtype=np.float64)
 def transform(self,x,W=None):
  cs,_=covariances(x,self.Ws if W is None else W,self.account)
  return (self.tangent(cs)-self.mean)/self.scale
