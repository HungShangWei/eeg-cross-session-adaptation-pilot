"""Completed-buffer preprocessing. Float64, source-frozen nuisance fit."""
import hashlib
import numpy as np
from scipy.signal import butter,sosfiltfilt,resample_poly
class SignalError(ValueError):pass
SOS=butter(N=4,Wn=[8,32],btype="bandpass",fs=250,output="sos")
if SOS.shape!=(4,6):raise SignalError("SOS_SHAPE")
SOS_SHA256=hashlib.sha256(np.asarray(SOS,dtype="<f8").tobytes(order="C")).hexdigest()
def filtered(raw,n):
 x=np.asarray(raw,dtype=np.float64)
 if x.shape!=(6,n) or not np.isfinite(x).all():raise SignalError("BUFFER_SHAPE_FINITE")
 x=x-x.mean(axis=1,keepdims=True)
 x=sosfiltfilt(SOS,x,axis=-1,padtype="odd",padlen=27)
 return x-x.mean(axis=1,keepdims=True)
def conditioning(g):
 e=np.linalg.eigvalsh((g+g.T)/2);rank=int(np.linalg.matrix_rank(g))
 return {"eigenvalues":e.tolist(),"rank":rank,"condition":float(e[-1]/e[0]) if rank==3 and e[0]>0 else None,
         "reason":None if rank==3 and e[0]>0 else "singular_infinite_condition"}
def removed_variance(f,B):
 X=f[:3].T;E=f[3:].T;fit=E@B;corr=X-fit
 a=X.var(axis=0);b=corr.var(axis=0);v=fit.var(axis=0)
 return {"raw_variance":a.tolist(),"corrected_variance":b.tolist(),"regression_variance":v.tolist(),
  "removed_fraction":[float(1-b[i]/a[i]) if a[i]>0 else None for i in range(3)],
  "null_reasons":[None if a[i]>0 else "zero_denominator" for i in range(3)]}
def rails(raw,units_verified):
 if not units_verified:return {"status":"not_evaluable","reason":"units_unverified"}
 x=np.asarray(raw,dtype=np.float64);out=[]
 for i in range(6):
  a=x[i];ok=np.isfinite(a);near=49 if i<3 else 980;nominal=50 if i<3 else 1000;n=int(ok.sum())
  out.append({"finite":n,"nonfinite":int((~ok).sum()),"positive_near":int((a[ok]>=near).sum()),
   "negative_near":int((a[ok]<=-near).sum()),"joint_near":int((abs(a[ok])>=near).sum()),
   "beyond_nominal":int((abs(a[ok])>nominal).sum()),"units":"microvolts"})
 return {"status":"descriptive_only","channels":out}
class Pipeline:
 def fit_nuisance(self,precue,ids):
  if len(precue)!=len(ids) or len(precue)<20:raise SignalError("PRE_CUE_BLOCK_GATE")
  fs=[filtered(x,500) for x in precue]
  E=np.concatenate([a[3:].T for a in fs]);X=np.concatenate([a[:3].T for a in fs])
  G=E.T@E;tr=float(np.trace(G))
  if not np.isfinite(tr) or tr<=0:raise SignalError("EOG_TRACE")
  lam=.001*tr/3;self.B=np.linalg.solve(G+lam*np.eye(3),E.T@X)
  if not np.isfinite(self.B).all():raise SignalError("NUISANCE_NONFINITE")
  self.nuisance={"ids":list(ids),"blocks":len(fs),"samples":len(E),"units":"microvolts","lambda":lam,
   "eog_population_variance":E.var(axis=0).tolist(),"gram":conditioning(G),"ridge_gram":conditioning(G+lam*np.eye(3)),
   "removed_variance":[removed_variance(f,self.B) for f in fs],"B":self.B.tolist(),"sos_sha256":SOS_SHA256}
  return self
 def transform(self,raw):
  f=filtered(raw,1125);x=f[:3]-(f[3:].T@self.B).T
  x=resample_poly(x,up=64,down=125,axis=-1,window=("kaiser",5.0),padtype="constant",cval=0)
  if x.shape!=(3,576):raise SignalError("RESAMPLE_SHAPE")
  x=x[:,64:576];x-=x.mean(axis=1,keepdims=True)
  if not np.isfinite(x).all() or float(np.sum(x*x))<=0:raise SignalError("COMMON_STRUCTURAL_INVALIDITY")
  return x
 def fit_scaler(self,x):
  a=np.asarray(x,dtype=np.float64)
  if a.ndim!=3 or a.shape[1:]!=(3,512) or not np.isfinite(a).all():raise SignalError("SCALER_INPUT")
  self.mean=a.mean(axis=(0,2));std=a.std(axis=(0,2))
  if (std==0).any():raise SignalError("FLAT_SOURCE_CHANNEL")
  self.floor=(std<1e-6);self.std=np.maximum(std,1e-6)
  return self
 def neural(self,x):return ((np.asarray(x,dtype=np.float64)-self.mean[None,:,None])/self.std[None,:,None]).astype(np.float32)
