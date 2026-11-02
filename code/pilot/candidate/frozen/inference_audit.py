"""Inference audit wrappers. No fitting, resampling or eager scientific import."""
import math,itertools
from contracts import label_usage,ValidityStop
def hp2_expected(gain,useful,active):
 if gain=='ESTABLISHED':
  return {(True,True):'HP2_SUPPORTED',(True,False):'GAIN_WITH_INADEQUATE_ACTIVE_FITTING',
   (False,True):'MEANINGFUL_GAIN_BUT_USEFULNESS_NOT_ESTABLISHED',(False,False):'MEANINGFUL_GAIN_BUT_USEFULNESS_AND_FITTING_NOT_ESTABLISHED'}[(useful,active)]
 if gain=='EXCLUDED_AGAINST_AT_LEAST_ONE_CONTROL':return 'HP2_MEANINGFUL_GAIN_EXCLUDED_FOR_THIS_COMPOSITE'
 if gain=='INCONCLUSIVE':return 'HP2_GAIN_INCONCLUSIVE'
 raise ValidityStop('GAIN')
HP2_EXPECTED=tuple((gain,u,a,hp2_expected(gain,u,a)) for gain in ('ESTABLISHED','EXCLUDED_AGAINST_AT_LEAST_ONE_CONTROL','INCONCLUSIVE') for u,a in itertools.product((False,True),repeat=2))
def finite_nine(*arrays):
 return all(len(a)==9 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in a) for a in arrays)
def unavailable(reason):return {'status':'NOT_EVALUABLE','reason':reason,'statistic':None}
def safe_usefulness(J,C,calculate=None):
 if not finite_nine(J,C):return unavailable('required_complete_nine_person_J_C_statistic_unavailable')
 if calculate is None:
  from statistics_recipe import usefulness
  calculate=usefulness
 try:return dict(status='EVALUATED',**calculate(J,C))
 except (ValueError,ArithmeticError) as exc:return unavailable('defining_statistic_unavailable:'+type(exc).__name__)
def audited_descriptive(JH,controls,coverages,indices,label_events,recipients,calculate=None):
 if set(controls)!=set(('N','EA-U')) or set(coverages)!=set(controls) or set(recipients)!=set(controls):return unavailable('both_prelisted_controls_required')
 if calculate is None:
  from inference_contract import descriptive_both
  calculate=descriptive_both
 result={}
 for name in ('N','EA-U'):
  audits=[label_usage(label_events,r) for r in recipients[name]]
  if not audits or any(x['status']!='EVALUATED' for x in audits):
   result[name]=unavailable('label_access_account_incomplete');continue
  acquired=sum(x['acquired'] for x in audits);used=sum(x['used'] for x in audits)
  if acquired or used:
   result[name]=dict(unavailable('no_label_control_received_or_used_labels'),target_labels_acquired=acquired,target_labels_used=used);continue
  if not finite_nine(JH,controls[name],coverages[name]):
   result[name]=unavailable('required_nine_person_statistic_unavailable');continue
  try:
   raw=calculate(JH,controls,coverages,indices)[name]
   raw.pop('target_labels',None)
   result[name]=dict(raw,target_labels_acquired=acquired,target_labels_used=used,label_account='observed_complete')
  except (ValueError,ArithmeticError) as exc:result[name]=unavailable('defining_statistic_unavailable:'+type(exc).__name__)
 return result
def hp2_checked(JL,CL,controls,fits,indices,ea=False,calculate=None):
 if set(controls)!=set(('K','N','EA-U')) or not finite_nine(JL,CL,*controls.values()):return unavailable('complete_nine_person_three_control_statistics_required')
 if calculate is None:
  from inference_contract import hp2
  calculate=hp2
 try:return calculate(JL,CL,controls,fits,indices,ea=ea)
 except (ValueError,ArithmeticError) as exc:return unavailable('defining_statistic_unavailable:'+type(exc).__name__)
