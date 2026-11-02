"""Explicit finite float64 objectives; conservative source restoration on failure."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp,expit
from contracts import ValidityStop,DevelopmentStop
from operations import ratio_grid,returned_gradient_norm
class SolverError(ValueError):pass
class EvaluationLimit(RuntimeError):pass
def labels(y):
 y=np.asarray(y,dtype=np.int64)
 if y.ndim!=1 or not np.isin(y,[0,1]).all():raise ValidityStop("LABEL_DOMAIN")
 return y
def ce(z,y):
 z=np.asarray(z,dtype=np.float64);y=labels(y)
 if z.shape!=(len(y),2) or not len(y) or not np.isfinite(z).all():raise SolverError("LOGITS")
 return float(np.mean(logsumexp(z,axis=1)-z[np.arange(len(y)),y]))
def eligible(y):return len(y)>=4 and len(np.unique(labels(y)))==2
def choose_grid(grid,values):
 v=np.asarray(values,dtype=np.float64)
 if not np.isfinite(v).all():raise SolverError("GRID_NONFINITE")
 ids=np.flatnonzero(v<=v.min()+1e-12)
 return min(ids,key=lambda i:(abs(grid[i]),grid[i]))
def temperature(z,y,Ts=1,source=False,R=2,penalty=1):
 y=labels(y);z=np.asarray(z,dtype=np.float64)
 if z.shape!=(len(y),2):raise ValidityStop("LOGIT_LABEL_SHAPE")
 if not np.isfinite(Ts) or Ts<=0:raise ValidityStop("SOURCE_T")
 if not eligible(y):
  return (1. if source else Ts),{"status":"source_calibration_insufficient" if source else "prefix_labels_insufficient","active":False,"fallback":True,"evaluations":0,"inspected_labels":len(y)}
 if source:
  grid=np.linspace(np.log(.5),np.log(5.),401)
  if not np.any(grid==0):grid=np.sort(np.r_[grid,0.])
  penalty=.1;Ts=1.
 else:grid=np.asarray(ratio_grid(R),dtype=np.float64)
 values=[];evaluations=0
 try:
  for u in grid:
   evaluations+=1;value=ce(z/(Ts*np.exp(u)),y)+penalty*u*u
   if not np.isfinite(value):raise SolverError("TEMPERATURE_NONFINITE_OBJECTIVE")
   values.append(value)
  j=choose_grid(grid,values);T=float(Ts*np.exp(grid[j]))
  if not np.isfinite(T) or T<=0:raise SolverError("TEMPERATURE_NONFINITE_OUTPUT")
  return T,{"status":"completed","active":True,"fallback":False,"evaluations":evaluations,"objective_values":values,
   "log_grid":grid.tolist(),"chosen_index":int(j),"boundary":j in (0,len(grid)-1),"inspected_labels":len(y)}
 except (SolverError,FloatingPointError,OverflowError) as exc:
  if source:raise DevelopmentStop("SOURCE_TEMPERATURE_NUMERICAL_FAILURE") from exc
  return Ts,{"status":"temperature_fit_failed_fallback_Ts","active":False,"fallback":True,"reason":str(exc),
   "evaluations":evaluations,"objective_values":values,"log_grid":grid.tolist(),"inspected_labels":len(y)}
def _solve(fun,x0,maxiter,maxfun,minimizer=None):
 evaluations=0;last=None;last_gradient=None
 def f(x):
  nonlocal evaluations,last,last_gradient
  if evaluations>=maxfun:raise EvaluationLimit("FUNCTION_EVALUATION_CAP")
  evaluations+=1;value,gradient=fun(x)
  last_gradient=np.asarray(gradient,dtype=np.float64).copy()
  if not np.isfinite(value) or not np.isfinite(last_gradient).all():raise SolverError("SOLVER_NONFINITE")
  last=float(value);return last,last_gradient
 try:
  solve=minimize if minimizer is None else minimizer
  r=solve(f,np.asarray(x0,dtype=np.float64),method="L-BFGS-B",jac=True,
   options={"maxiter":maxiter,"maxfun":maxfun,"gtol":1e-6,"ftol":1e-12,"maxls":20})
  ok=bool(bool(r.success) and np.isfinite(r.x).all())
  norm,source=returned_gradient_norm(r,last_gradient)
  return r.x if ok else np.array(x0,copy=True),{"status":"completed" if ok else "truncated_or_failed_fallback","active":ok,
   "iterations":int(r.nit),"evaluations":evaluations,"gradient_evaluations":evaluations,"message":str(r.message),
   "last_objective":last,"final_gradient_norm":norm,"final_gradient_source":source}
 except (EvaluationLimit,SolverError,FloatingPointError,OverflowError) as exc:
  norm,source=returned_gradient_norm(None,last_gradient)
  return np.array(x0,copy=True),{"status":"failed_fallback","active":False,"iterations":None,"evaluations":evaluations,
   "gradient_evaluations":evaluations,"message":str(exc),"last_objective":last,
   "final_gradient_norm":norm,"final_gradient_source":source}
def head_objective(x,f,y,W0,b0,Ts,lam):
 W=x[:-2].reshape(W0.shape);b=x[-2:];z=(f@W.T+b)/Ts
 loss=ce(z,y)+lam/2*(np.sum((W-W0)**2)+np.sum((b-b0)**2))
 p=np.exp(z-logsumexp(z,axis=1,keepdims=True));p[np.arange(len(y)),y]-=1;p/=len(y)*Ts
 return loss,np.r_[(p.T@f+lam*(W-W0)).ravel(),p.sum(axis=0)+lam*(b-b0)]
def fit_head(f,y,W0,b0,Ts,lam=.1,maxiter=100,maxfun=1000):
 f=np.asarray(f,dtype=np.float64);y=labels(y)
 if not eligible(y):return W0.copy(),b0.copy(),{"status":"prefix_labels_insufficient","active":False,"fallback":True,"evaluations":0,"inspected_labels":len(y)}
 x0=np.r_[W0.ravel(),b0]
 x,status=_solve(lambda x:head_objective(x,f,y,W0,b0,Ts,lam),x0,maxiter,maxfun)
 status["inspected_labels"]=len(y)
 if not status["active"]:status.update(status="head_fit_failed_fallback_K",fallback=True)
 else:status["fallback"]=False
 return x[:-2].reshape(W0.shape),x[-2:],status
def logistic_objective(x,hs,ys,lam,ht=None,yt=None,rho=0):
 w=x[:-1];b=x[-1];loss=lam/2*np.dot(w,w);grad=np.r_[lam*w,0.]
 for h,y,weight in [(hs,ys,1-rho),(ht,yt,rho)]:
  if not weight:continue
  g=h@w+b;loss+=weight*np.mean(np.logaddexp(0,g)-y*g);r=(expit(g)-y)*weight/len(y)
  grad+=np.r_[h.T@r,r.sum()]
 return float(loss),grad
def logistic(hs,ys,lam=.1,source=None,ht=None,yt=None,rho=.25,maxiter=200,maxfun=2000):
 hs=np.asarray(hs,dtype=np.float64);ys=labels(ys)
 if source is None:
  x0=np.zeros(hs.shape[1]+1);rho=0
 else:
  x0=np.asarray(source,dtype=np.float64).copy();yt=labels(yt)
  if not eligible(yt):return x0,{"status":"prefix_labels_insufficient","active":False,"evaluations":0,"inspected_labels":len(yt)}
  ht=np.asarray(ht,dtype=np.float64)
 x,status=_solve(lambda x:logistic_objective(x,hs,ys,lam,ht,yt,rho),x0,maxiter,maxfun)
 status["source_label_replay"]=len(ys);status["inspected_labels"]=0 if source is None else len(yt)
 if source is not None and not status["active"]:status.update(status="EA_L_failed_fallback_EA_U",fallback=True)
 return x,status
