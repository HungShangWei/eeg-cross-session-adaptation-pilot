"""Numerical fallback routing only. Resource/permission/validity stops are never swallowed."""
import copy,math
from contracts import NumericalFailure,ValidityStop,DevelopmentStop
FLAGS={'N':'normalization_failed_fallback_K','T':'temperature_fit_failed_fallback_Ts','H':'head_fit_failed_fallback_K','EA-L':'EA_L_failed_fallback_EA_U'}
SKIPS={'N':'prefix_features_insufficient','T':'prefix_labels_insufficient','H':'prefix_labels_insufficient','EA-L':'prefix_labels_insufficient','source_temperature':'source_calibration_insufficient'}
def atomic_operation(name,source,apply,eligible=True,context='target',clone=copy.deepcopy,validate=lambda x:True):
 if name not in FLAGS:raise ValidityStop('OPERATION')
 original=clone(source)
 if not eligible:return clone(original),{'status':SKIPS[name],'active':False,'fallback':True,'reason':'insufficient_eligible_examples'}
 try:
  result,status=apply(clone(original))
  if not validate(result):raise NumericalFailure('NONFINITE_OPERATION_RESULT')
  if not status.get('active',False):
   if context=='development' and status.get('status') not in set(SKIPS.values()):raise DevelopmentStop('FAILED_CANDIDATE_NOT_ELIGIBLE_FOR_SELECTION')
   return clone(original),dict(status,status=FLAGS[name],fallback=True,active=False)
  return result,dict(status,fallback=False)
 except NumericalFailure as exc:
  if context=='development':raise DevelopmentStop('NUMERICAL_CANDIDATE_FAILURE') from exc
  return clone(original),{'status':FLAGS[name],'active':False,'fallback':True,'reason':str(exc)}
def candidate_ok(status):
 allowed=set(SKIPS.values())|{'alignment_prefix_insufficient'}
 if not status.get('active') and status.get('status') not in allowed:raise DevelopmentStop('FAILED_CANDIDATE_NOT_ELIGIBLE_FOR_SELECTION')
def ratio_grid(R):
 if R not in (2,4):raise ValidityStop('FIXED_RATIO_GRID')
 bound=math.log(R);grid=tuple(i*bound/200 for i in range(-200,201))
 if len(grid)!=401 or grid[200]!=0.0 or grid[0]!=-bound or grid[-1]!=bound:raise ValidityStop('GRID_CONTRACT')
 return grid
def returned_gradient_norm(result,last_gradient):
 """Use solver-returned jac; otherwise previously evaluated gradient. Never call objective."""
 g=getattr(result,'jac',None) if result is not None else None
 source='solver_returned_jac'
 if g is None:g=last_gradient;source='last_evaluated_gradient'
 if g is None:return None,'not_available_no_evaluation'
 flat=list(g)
 if not all(math.isfinite(float(v)) for v in flat):return None,'nonfinite_existing_gradient'
 return math.hypot(*(float(v) for v in flat)),source
