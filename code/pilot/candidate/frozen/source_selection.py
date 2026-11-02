"""Full formal recipe choices as pure cached-score selectors; formal execution disabled."""
import itertools
import numpy as np
from science_contract import formal_entry
CHECKPOINTS=(25,50,100)
GRIDS={'N':tuple((k,) for k in (0,40,160)),'T':tuple(itertools.product((2,4),(.1,1.))),
 'H':tuple((v,) for v in (.01,.1,1.)),'EA_source':tuple((v,) for v in (.01,.1,1.)),
 'EA_L':tuple((v,) for v in (.25,.50,.75))}
CONTEXT={'N':'D0_fixed','T':'D0_times_exp_D1','H':'D0_fixed','EA_source':'unscaled','EA_L':'EA_D0_fixed'}
def select_checkpoint(losses):
 a=np.asarray(losses,dtype=np.float64)
 if a.shape!=(3,3) or not np.isfinite(a).all():raise ValueError('COMPLETE_THREE_SEED_CHECKPOINT_GRID_REQUIRED')
 means=a.mean(axis=1);eligible=np.flatnonzero(means<=means.min()+1e-12)
 return CHECKPOINTS[int(eligible[0])]
def select_development(component,records,temperature_context):
 if component not in GRIDS or temperature_context!=CONTEXT[component]:raise ValueError('D2_TEMPERATURE_CONTEXT')
 expected=GRIDS[component]
 if set(records)!=set(expected):raise ValueError('COMPLETE_PREDECLARED_GRID_REQUIRED')
 means={}
 for key,v in records.items():
  a=np.asarray(v,dtype=np.float64)
  expected_n=1 if component.startswith('EA') else 3
  if a.shape!=(expected_n,) or not np.isfinite(a).all():raise ValueError('CANDIDATE_FAILURE_BLOCKS_SELECTION')
  means[key]=float(a.mean())
 best=min(means.values());tied=[k for k,v in means.items() if v<=best+1e-12]
 if component=='T':winner=min(tied,key=lambda k:(-k[1],k[0]))
 elif component=='EA_L':winner=min(tied)
 else:winner=max(tied)
 return {'selected':winner,'all_scores':[{'parameters':k,'mean_D2_loss':v} for k,v in means.items()],'temperature_context':temperature_context,'development_uninformative':len(set(means.values()))==1}
def formal_source_plan():
 return {'enabled':False,'participants':list(range(1,10)),'seeds':[1103,2207,3301],
 'epochs':100,'training_batch':32,'checkpoints':list(CHECKPOINTS),'optimizer':'AdamW lr.001 betas(.9,.999) eps1e-8 decay.0001 foreachFalse fusedFalse',
 'checkpoint_score':'mean unscaled D2 NLL over three seeds','BN':'evaluation copies, canonical layer-order source-only',
 'development_context':CONTEXT,'calibration':'S-cal after all source choices frozen',
 'source_gate':'>=48 valid Sfit; >=12/class; >=20 valid precue; >=10 D2',
 'source_final_refit':False,'failure':'stop whole affected stage, do not choose among surviving candidates',
 'execution_implementation':'NOT_COMPLETE; E3 entry remains disabled'}
def execute_formal_source(*args,**kwargs):formal_entry()
