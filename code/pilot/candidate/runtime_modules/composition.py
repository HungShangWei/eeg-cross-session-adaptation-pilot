"""Shared adaptation/prediction composition; explicit views/state/dependencies only.
No provider, path, dataset, model creation, approval fabrication or cache.
"""
import copy
from contracts import ValidityStop,Block
def adapt_core(source,op,d,view,deps):
 deps.guard()
 if op not in ('K','N','T','H','EA-U','EA-L') or d not in (0,5,10,20,40):raise ValidityStop('OPERATION_BUDGET')
 state=copy.deepcopy(source);events=[]
 if op=='K':return state,events
 if op in ('T','H','EA-L') and d==0:raise ValidityStop('ZERO_BUDGET_REQUIRES_EXPLICIT_ALIAS')
 if not isinstance(view,Block):raise ValidityStop('CORE_BLOCK')
 expected=tuple(range(40 if op in ('N','EA-U','EA-L') else d))
 if view.requested!=expected:raise ValidityStop('CORE_FEATURE_OPPORTUNITIES')
 labels=() if op in ('N','EA-U') else tuple(range(d))
 if op in ('T','H'):deps.inspect_labels('schema_validation',view.labels.values)
 view.validate(labels)
 if view.labels.ordinals!=tuple(i for i in view.neural.ordinals if i in labels):raise ValidityStop('CORE_LABEL_JOIN')
 choice=state['choices']
 if op=='N':
  state['model'],state['status']=deps.update_n(state['model'],state['moments'],view.neural.values,choice['N']['selected'][0])
 elif op in ('T','H'):
  x=deps.take(view.neural.values,view.labelled_positions());y=view.labels.values
  f=deps.features(state['model'],x)
  events.append({'event':'labels_used','partition':'P','ordinals':view.labels.ordinals})
  if op=='T':
   R,penalty=choice['T']['selected']
   state['Ts'],state['status']=deps.temperature(deps.head_logits(f,state['W'],state['b']),y,Ts=state['Ts'],R=R,penalty=penalty)
  else:state['W'],state['b'],state['status']=deps.fit_head(f,y,state['W'],state['b'],state['Ts'],lam=choice['H']['selected'][0])
 else:
  # Each EA arm independently derives Wt from its own complete legal prefix.
  ws=state['ea'].Ws
  wt,alignment=deps.prefix_whitening(view.corrected_uV.values,ws)
  state['Ws']=wt
  state['alignment']={'prefix_ordinals':view.corrected_uV.ordinals,'prefix_identity':deps.identity(view.corrected_uV.values),
   'source_Ws_identity':deps.identity(ws),'Wt_identity':deps.identity(wt),'status':alignment}
  if op=='EA-U':state['status']=alignment
  else:
   raw=deps.take(view.corrected_uV.values,view.labelled_positions())
   ht=deps.ea_transform(state['ea'],raw,wt)
   events.append({'event':'labels_used','partition':'P','ordinals':view.labels.ordinals})
   state['coef'],state['status']=deps.logistic(state['ea'].source_features,state['ys'],lam=choice['EA_source']['selected'][0],
    source=state['coef'],ht=ht,yt=view.labels.values,rho=choice['EA_L']['selected'][0])
 return state,events
def predict_core(state,q,block,deps):
 deps.guard()
 if block.requested!=tuple(q):raise ValidityStop('Q_IDENTITY')
 block.validate(())
 if block.labels.ordinals:raise PermissionError('Q_LABELS_BEFORE_SEAL')
 if state['kind']=='neural':
  f=deps.features(state['model'],block.neural.values);gap=deps.neural_gap(f,state['W'],state['b'])
 else:
  h=deps.ea_transform(state['ea'],block.corrected_uV.values,state['Ws']);gap=deps.ea_gap(h,state['coef'])
 return deps.prediction_payload(q,block.neural.ordinals,gap)
