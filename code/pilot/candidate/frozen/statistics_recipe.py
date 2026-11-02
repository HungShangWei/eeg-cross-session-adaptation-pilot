"""Synthetic-only evaluator verification and fixed person-level statistics."""
import hashlib,itertools
import numpy as np
from scipy.stats import t
from scipy.special import expit
class StatsError(ValueError):pass
def score_synthetic(gap,y,valid,T=1,cost=.25,partition="Q",sealed=False):
 if partition!="Q" or not sealed:raise PermissionError("PREDICTION_SEAL_REQUIRED")
 gap=np.asarray(gap,dtype=np.float64);y=np.asarray(y,dtype=np.int64);valid=np.asarray(valid,dtype=bool)
 if gap.ndim!=1 or not(gap.shape==y.shape==valid.shape) or len(y)==0 or not np.isin(y,[0,1]).all():raise StatsError("SCORING_SCHEMA")
 if T<=0 or not np.isfinite(T) or cost not in (.1,.25,.4):raise StatsError("DECISION_SETTINGS")
 if np.any(valid & ~np.isfinite(gap)):raise StatsError("VALID_NONFINITE")
 predicted=gap>0;accept=valid & (np.abs(gap)/T>=np.log((1-cost)/cost))
 err=(predicted!=y);n=len(y);a=int(accept.sum());loss=np.where(accept,err.astype(np.float64),cost)
 p=expit(gap[valid]/T);yv=y[valid];nv=len(yv)
 accuracy=float(np.mean((predicted[valid]==yv))) if nv else None
 recalls=[float(np.mean(predicted[valid][yv==k]==k)) if np.any(yv==k) else None for k in (0,1)]
 if nv:
  observed=accuracy;expected=sum(float(np.mean(yv==k)*np.mean(predicted[valid]==k)) for k in (0,1))
  kappa=(observed-expected)/(1-expected) if expected<1 else None
 else:kappa=None
 return {"J":float(loss.mean()),"C":a/n,"R":float(err[accept].mean()) if a else None,"R_null_reason":None if a else "zero_accepted",
  "denominator":n,"accepted":a,"accepted_wrong":int(err[accept].sum()),"deferred":n-a,"technical_deferred":int((~valid).sum()),"valid":nv,
  "accuracy":accuracy,"balanced_accuracy":float(np.mean(recalls)) if all(x is not None for x in recalls) else None,"kappa":kappa,
  "NLL":float(np.mean(np.logaddexp(0,gap[valid]/T)-yv*gap[valid]/T)) if nv else None,
  "Brier":float(np.mean((p-yv)**2)) if nv else None}
def person_means(a):
 a=np.asarray(a,dtype=np.float64)
 if a.shape!=(9,3) or not np.isfinite(a).all():raise StatsError("NINE_PEOPLE_THREE_SEEDS")
 return a.mean(axis=1)
def bounds(x,alpha=.025):
 x=np.asarray(x,dtype=np.float64)
 if x.shape!=(9,) or not np.isfinite(x).all():raise StatsError("COMPLETE_NINE_PERSON_DATA")
 mean=float(x.mean());sd=float(x.std(ddof=1));se=sd/3
 return {"mean":mean,"lower":float(mean-t.ppf(1-alpha,8)*se),"upper":float(mean+t.ppf(1-alpha,8)*se),
 "two_sided95":[float(mean-t.ppf(.975,8)*se),float(mean+t.ppf(.975,8)*se)],"degenerate_sd":sd==0,"n":9,"df":8,"alpha":alpha}
def ni_category(delta):
 if delta["upper"]<.02:return "ESTABLISHED"
 if delta["lower"]>.02:return "CONTRADICTED"
 return "INCONCLUSIVE"
def usefulness(J,C,alpha=.025):
 jb=bounds(J,alpha);cb=bounds(C,alpha);guard=int(np.sum((np.asarray(J)<=.2)&(np.asarray(C)>=.5)))
 reasons=[]
 if jb["upper"]>=.2:reasons.append("J_bound_failed")
 if cb["lower"]<=.5:reasons.append("C_bound_failed")
 if guard<7:reasons.append("7_of_9_failed")
 against=jb["lower"]>.2 or cb["upper"]<.5
 return {"established":not reasons,"J":jb,"C":cb,"participant_guard":guard,"reasons":reasons,
 "interpretation":"evidence_against_utility_bound" if against else "utility_not_established_with_current_precision" if reasons else "useful_established"}
def active_guard(fits,ea=False):
 a=np.asarray(fits,dtype=bool)
 if a.shape!=((9,) if ea else (9,3)):raise StatsError("ACTIVE_FIT_SHAPE")
 count=int(np.sum(a if ea else a.sum(axis=1)>=2));return count>=6,count
def hp1_label(ni,ut,uh,active):
 suffix=f"__T{int(ut)}_H{int(uh)}_A{int(active)}"
 if ni=="CONTRADICTED":base="HP1_NI_CONTRADICTED"
 elif ni=="INCONCLUSIVE":base="HP1_NI_INCONCLUSIVE"
 elif ni=="ESTABLISHED":
  if ut and active:base="HP1_SUPPORTED"
  elif ut:base="NI_T_FIT_INADEQUATE"
  elif active:base="NI_T_USEFUL_NOT_ESTABLISHED"
  else:base="NI_T_USEFUL_NOT_ESTABLISHED_AND_FIT_INADEQUATE"
 else:raise StatsError("NI_ENUM")
 return base+suffix
def gain_status(differences):
 bs=[bounds(x,.025/3) for x in differences]
 if len(bs)!=3:raise StatsError("THREE_FIXED_CONTROLS")
 if all(b["upper"]<-.02 for b in bs):return "ESTABLISHED"
 if any(b["lower"]>-.02 for b in bs):return "EXCLUDED_AGAINST_AT_LEAST_ONE_CONTROL"
 return "INCONCLUSIVE"
def hp2_label(gain,useful,active):
 if gain=="ESTABLISHED":
  return {(True,True):"HP2_SUPPORTED",(True,False):"GAIN_WITH_INADEQUATE_ACTIVE_FITTING",
   (False,True):"MEANINGFUL_GAIN_BUT_USEFULNESS_NOT_ESTABLISHED",(False,False):"MEANINGFUL_GAIN_BUT_USEFULNESS_AND_FITTING_NOT_ESTABLISHED"}[(bool(useful),bool(active))]
 if gain=="EXCLUDED_AGAINST_AT_LEAST_ONE_CONTROL":return "HP2_MEANINGFUL_GAIN_EXCLUDED_FOR_THIS_COMPOSITE"
 if gain=="INCONCLUSIVE":return "HP2_GAIN_INCONCLUSIVE"
 raise StatsError("GAIN_ENUM")
def bootstrap_indices(charge):
 charge("resample_fixture",1);charge("resamples",10000)
 return np.random.Generator(np.random.PCG64(20260926)).integers(0,9,size=(10000,9),dtype=np.int64)
def percentile(x,indices,alpha=.025):
 a=np.asarray(x,dtype=np.float64)
 if a.shape!=(9,) or indices.shape!=(10000,9):raise StatsError("RESAMPLE_SCHEMA")
 means=a[indices].mean(axis=1)
 return {"lower":float(np.quantile(means,alpha,method="linear")),"upper":float(np.quantile(means,1-alpha,method="linear")),
  "two_sided95":np.quantile(means,[.025,.975],method="linear").tolist()}
def robustness(base_supported,required_passes):
 if any(v is None for v in required_passes):return "robustness_not_evaluable"
 if not base_supported:return "no_bootstrap_upgrade"
 return "robust" if all(required_passes) else "MODEL_DEPENDENT"
def change_fractions(k_gap,o_gap,kT,oT,kvalid,ovalid,cost=.25):
 kv=np.asarray(kvalid,dtype=bool);ov=np.asarray(ovalid,dtype=bool)
 common=kv&ov
 if not np.array_equal(kv,ov):return {"status":"unknown","reason":"missing_mask_mismatch"}
 if not common.any():return {"status":"unknown","reason":"no_common_valid"}
 k=np.asarray(k_gap)[common];o=np.asarray(o_gap)[common]
 class_change=(k>0)!=(o>0);b=np.log((1-cost)/cost);accept_change=(abs(k)/kT>=b)!=(abs(o)/oT>=b)
 return {"status":"computed","denominator":int(common.sum()),"class_numerator":int(class_change.sum()),"accept_numerator":int(accept_change.sum()),
  "union_numerator":int((class_change|accept_change).sum()),"union_fraction":float(np.mean(class_change|accept_change))}
def near_inactive(qT,qH):
 a=np.asarray(qT,dtype=float);b=np.asarray(qH,dtype=float)
 if a.shape!=(9,) or b.shape!=(9,):raise StatsError("NEAR_INACTIVE_SHAPE")
 known=np.isfinite(a)&np.isfinite(b);n=int(np.sum(known&(a<.02)&(b<.02)));unknown=int((~known).sum())
 return {"status":"yes" if n>=5 else "no" if n+unknown<5 else "unknown","qualifying_people":n,"unknown_people":unknown}
