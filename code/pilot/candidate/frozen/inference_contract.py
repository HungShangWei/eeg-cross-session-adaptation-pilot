"""E1-A/1.1 participant-level composite logic, no data loading or resampling."""
import numpy as np
from statistics_recipe import bounds,percentile,usefulness,active_guard,ni_category,hp1_label,hp2_label,robustness
def _complete(*args):
 return all(np.asarray(a).shape==(9,) and np.isfinite(np.asarray(a,dtype=float)).all() for a in args)
def hp1(JT,JH,CT,CH,Tfits,Hfits,indices):
 if not _complete(JT,JH,CT,CH):return {'status':'NOT_EVALUABLE','reason':'complete_nine_person_summaries_required'}
 delta=np.asarray(JT)-np.asarray(JH);db=bounds(delta);ni=ni_category(db)
 ut=usefulness(JT,CT);uh=usefulness(JH,CH);at,nt=active_guard(Tfits);ah,nh=active_guard(Hfits)
 label=hp1_label(ni,ut['established'],uh['established'],at)
 boot={'delta':percentile(delta,indices),'T_J':percentile(JT,indices),'T_C':percentile(CT,indices),
       'H_J':percentile(JH,indices),'H_C':percentile(CH,indices)} if indices is not None else None
 passes=[boot['delta']['upper']<.02,boot['T_J']['upper']<.20,boot['T_C']['lower']>.50] if boot else [None]
 supported=label.startswith('HP1_SUPPORTED')
 return {'status':'EVALUATED','t_model_base_label':label,'delta':db,'NI':ni,'T_usefulness':ut,'H_usefulness':uh,
 'T_active_people':nt,'H_active_people':nh,'H_useful_fitted_reference':bool(uh['established'] and ah),
 'H_reference_robustness':robustness(uh['established'],[boot['H_J']['upper']<.20,boot['H_C']['lower']>.50] if boot else [None]),
 'bootstrap':boot,'robustness_status':robustness(supported,passes),
 'contradiction_model_dependent':bool(ni=='CONTRADICTED' and boot and not boot['delta']['lower']>.02)}
def hp2(JL,CL,controls,fits,indices,ea=False):
 if set(controls)!=set(('K','N','EA-U')) or not _complete(JL,CL,*controls.values()):return {'status':'NOT_EVALUABLE'}
 alpha=.025/3;diff={k:np.asarray(JL)-np.asarray(v) for k,v in controls.items()};b={k:bounds(v,alpha) for k,v in diff.items()}
 excluded=[k for k,v in b.items() if v['lower']>-.02]
 gain='ESTABLISHED' if all(v['upper']<-.02 for v in b.values()) else 'EXCLUDED_AGAINST_AT_LEAST_ONE_CONTROL' if excluded else 'INCONCLUSIVE'
 use=usefulness(JL,CL,alpha);active,n=active_guard(fits,ea);base=hp2_label(gain,use['established'],active)
 boot={k:percentile(v,indices,alpha) for k,v in diff.items()} if indices is not None else None
 if boot:boot.update(J=percentile(JL,indices,alpha),C=percentile(CL,indices,alpha))
 passes=[*[boot[k]['upper']<-.02 for k in controls],boot['J']['upper']<.20,boot['C']['lower']>.50] if boot else [None]
 return {'status':'EVALUATED','alpha_candidate':alpha,'t_model_base_label':base,'gain_status':gain,'candidate_usefulness':use,
 'active_fit_status':active,'active_people':n,'excluded_controls':excluded,'all_three_contrasts':b,'bootstrap':boot,
 'robustness_status':robustness(base=='HP2_SUPPORTED',passes),'nine_difference_intervals_simultaneous':False}
def descriptive_both(JH,controls,coverages,indices):
 if set(controls)!=set(('N','EA-U')) or set(coverages)!=set(controls):return {'status':'NOT_EVALUABLE'}
 result={}
 for key,j in controls.items():
  if not _complete(JH,j,coverages[key]):result[key]={'status':'NOT_EVALUABLE'};continue
  delta=np.asarray(j)-np.asarray(JH);b=bounds(delta);u=usefulness(j,coverages[key]);support=b['upper']<.02 and u['established']
  boot=[percentile(delta,indices)['upper']<.02,percentile(j,indices)['upper']<.20,percentile(coverages[key],indices)['lower']>.50] if indices is not None else [None]
  result[key]={'label':'DESCRIPTIVE_NO_LABEL_COMPETITIVE' if support else 'DESCRIPTIVE_INCONCLUSIVE','delta':b,'usefulness':u,
   'robustness':robustness(support,boot),'confirmatory':False,'FWE_control_claimed':False,'target_labels':0}
 return result
