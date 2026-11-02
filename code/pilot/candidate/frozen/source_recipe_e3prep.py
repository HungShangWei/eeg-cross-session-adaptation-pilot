"""E1-A/1.1 full source recipe for static review. E2 entry always rejects before data access.
non_formal=true; formal_execution_authorized=false; publishable_as_pilot_results=false.
No formal command is registered. This body has NOT been run under initial E2.
"""
import copy,random
import numpy as np
import torch
from science_contract import SEED_BASES
from contracts import Block,ValidityStop,DevelopmentStop,digest,validate_development
from operations import candidate_ok as _candidate_ok
from source_selection import CHECKPOINTS,GRIDS,CONTEXT,select_checkpoint,select_development
from neural_recipe import setup,EEGNet,canonical,features,head_arrays,head_logits,update_n,state_hash
from solvers_recipe import ce,temperature,fit_head,logistic
from ea_recipe import EAFeatures,prefix_whitening
from array_edges import ea_transform
def _checked_block(block,maximum=None):
 if not isinstance(block,Block):raise ValidityStop('INDEXED_SOURCE_BLOCK')
 x=np.asarray(block.neural.values,dtype=np.float32);y=np.asarray(block.labels.values,dtype=np.int64)
 if x.shape!=(len(block.neural.ordinals),3,512) or not np.isfinite(x).all() or not np.isin(y,[0,1]).all():raise ValidityStop('SOURCE_BLOCK')
 if maximum is not None and len(block.requested)>maximum:raise ValidityStop('SOURCE_BLOCK_CAP')
 return x,y,block.neural.ordinals
def prepare_full_source(participant,broker,account,record,permit,code_sha256,source_blocks,binding):
 if permit.scope!='FORMAL' or permit.code_sha256!=code_sha256:raise PermissionError('E3_FORMAL_SOURCE_PERMISSION')
 from numeric_dependencies import NumericDependencies
 deps=NumericDependencies(account);forward_charge=deps
 temperature=deps.temperature;fit_head=deps.fit_head;logistic=deps.logistic
 if binding.get('status')!='DEVELOPMENT_BOUND' or binding.get('participant')!=participant or binding.get('broker_identity')!=broker.identity:raise ValidityStop('BOUND_DEVELOPMENT_REQUIRED')
 validate_development(source_blocks,broker.n_source)
 xf,yf,fitids=_checked_block(source_blocks['S-fit'])
 d0,y0,_=_checked_block(source_blocks['D0'],20);d1,y1,id1=_checked_block(source_blocks['D1'],20);d2,y2,_=_checked_block(source_blocks['D2'],20)
 if len(xf)<48 or min(np.sum(yf==0),np.sum(yf==1))<12 or len(d2)<10:raise ValidityStop('FORMAL_SOURCE_GATE')
 labelled=list(source_blocks['D1'].labelled_positions())
 candidates={};checkpoint_losses=np.empty((3,3),dtype=np.float64)
 for seed_index,base in enumerate(SEED_BASES):
  q=10000*participant+base;setup(q);model=account.new_model(participant,q,EEGNet)
  optimizer=torch.optim.AdamW(model.parameters(),lr=.001,betas=(.9,.999),eps=1e-8,weight_decay=.0001,foreach=False,fused=False)
  rng=np.random.Generator(np.random.PCG64(q));model.train()
  for epoch in range(1,101):
   order=rng.permutation(len(xf));losses=[]
   for start in range(0,len(order),32):
    ids=order[start:start+32]
    def train_step():
     x=torch.from_numpy(xf[ids,None]);y=torch.as_tensor(yf[ids],dtype=torch.long)
     optimizer.zero_grad(set_to_none=True);loss=torch.nn.functional.cross_entropy(model(x),y)
     if not torch.isfinite(loss):raise ValueError('SOURCE_NONFINITE_LOSS')
     loss.backward();optimizer.step();return float(loss.detach())
    losses.append(account.run('optimizer_step',{'participant':participant,'seed':q,'epoch':epoch,'ordinals':[fitids[int(j)] for j in ids]},train_step))
   record('epoch',{'participant':participant,'seed':q,'epoch':epoch,'losses':losses,
    'state':copy.deepcopy(model.state_dict()),'optimizer':copy.deepcopy(optimizer.state_dict()),
    'torch_rng':torch.get_rng_state().clone(),'numpy_rng':copy.deepcopy(rng.bit_generator.state),'python_rng':random.getstate()})
   if epoch in CHECKPOINTS:
    evaluation,mom=canonical(model,xf,forward_charge);W,b=head_arrays(evaluation)
    fd2=features(evaluation,d2,forward_charge);loss=ce(head_logits(fd2,W,b),y2)
    checkpoint_losses[CHECKPOINTS.index(epoch),seed_index]=loss
    candidates[(base,epoch)]=(evaluation,mom)
    record('checkpoint',{'seed':q,'epoch':epoch,'unscaled_D2_NLL':loss,'state_sha256':state_hash(evaluation)})
  account.end_trajectory()
 selected_epoch=select_checkpoint(checkpoint_losses);seeds=[]
 scores={name:{key:[] for key in GRIDS[name]} for name in ('N','T','H')}
 for base in SEED_BASES:
  model,mom=candidates[(base,selected_epoch)];W,b=head_arrays(model)
  f0=features(model,d0,forward_charge);f1=features(model,d1,forward_charge);f2=features(model,d2,forward_charge)
  T0,cal=temperature(head_logits(f0,W,b),y0,source=True);_candidate_ok(cal)
  for (k,) in GRIDS['N']:
   n,st=update_n(model,mom,d1,forward_charge,k=k);_candidate_ok(st)
   score=ce(head_logits(features(n,d2,forward_charge),W,b)/T0,y2);scores['N'][(k,)].append(score)
   record('development_N',{'seed':base,'k':k,'temperature':T0,'D2_NLL':score,'status':st})
  for R,penalty in GRIDS['T']:
   temp,st=temperature(head_logits(f1[labelled],W,b),y1,Ts=T0,R=R,penalty=penalty);_candidate_ok(st)
   score=ce(head_logits(f2,W,b)/temp,y2);scores['T'][(R,penalty)].append(score)
   record('development_T',{'seed':base,'R':R,'penalty':penalty,'temperature':temp,'D2_NLL':score,'status':st})
  for (penalty,) in GRIDS['H']:
   wh,bh,st=fit_head(f1[labelled],y1,W,b,T0,lam=penalty);_candidate_ok(st)
   score=ce(head_logits(f2,wh,bh)/T0,y2);scores['H'][(penalty,)].append(score)
   record('development_H',{'seed':base,'penalty':penalty,'temperature':T0,'D2_NLL':score,'status':st})
  seeds.append({'base':base,'model':model,'moments':mom,'source_W':W,'source_b':b,'provisional_D0_temperature':T0})
 choices={name:select_development(name,scores[name],CONTEXT[name]) for name in scores}
 # EA consumes unstandardized corrected microvolt epochs, supplied separately.
 raw_fit=np.asarray(source_blocks['S-fit'].corrected_uV.values,dtype=np.float64)
 ea=EAFeatures(account).fit(raw_fit);hd2=ea_transform(ea,source_blocks['D2'].corrected_uV.values);ea_candidates={};ea_scores={}
 for (lam,) in GRIDS['EA_source']:
  coef,st=logistic(ea.source_features,yf,lam=lam)
  if not st['active']:raise RuntimeError('EA_SOURCE_CANDIDATE_FAILED')
  score=ce(np.c_[np.zeros(len(hd2)),hd2@coef[:-1]+coef[-1]],y2)
  ea_scores[(lam,)]=[score];ea_candidates[lam]=coef
  record('development_EA_source',{'lambda':lam,'unscaled_D2_NLL':score,'status':st})
 choices['EA_source']=select_development('EA_source',ea_scores,CONTEXT['EA_source'])
 lam=choices['EA_source']['selected'][0];coef=ea_candidates[lam]
 hd0=ea_transform(ea,source_blocks['D0'].corrected_uV.values);T0EA,calEA=temperature(np.c_[np.zeros(len(hd0)),hd0@coef[:-1]+coef[-1]],y0,source=True);_candidate_ok(calEA)
 Wd1,st=prefix_whitening(source_blocks['D1'].corrected_uV.values,ea.Ws,account);_candidate_ok(st)
 hd1=ea_transform(ea,source_blocks['D1'].corrected_uV.values,Wd1);hd2=ea_transform(ea,source_blocks['D2'].corrected_uV.values,Wd1);rho_scores={}
 for (rho,) in GRIDS['EA_L']:
  updated,st=logistic(ea.source_features,yf,lam=lam,source=coef,ht=hd1[labelled],yt=y1,rho=rho);_candidate_ok(st)
  score=ce(np.c_[np.zeros(len(hd2)),hd2@updated[:-1]+updated[-1]]/T0EA,y2);rho_scores[(rho,)]=[score]
  record('development_EA_L',{'rho':rho,'temperature':T0EA,'D2_NLL':score,'status':st})
 choices['EA_L']=select_development('EA_L',rho_scores,CONTEXT['EA_L'])
 choices['checkpoint']={'selected':selected_epoch,'all_scores':checkpoint_losses.tolist(),'tie_rule':'earliest within 1e-12'}
 def frozen_hashes():
  def array_hash(a):
   import hashlib
   a=np.asarray(a);return hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
  states={str(item['base']):state_hash(item['model']) for item in seeds}
  states['EA']=digest({k:array_hash(v) for k,v in {'Ws':ea.Ws,'Q':ea.Q,'mean':ea.mean,'scale':ea.scale,'coef':coef}.items()})
  return states
 ties={key:{'scores':value.get('all_scores'),'selected':value['selected'],'tolerance':1e-12,
  'rule':'earliest_checkpoint' if key=='checkpoint' else 'stronger_penalty_then_smaller_R' if key=='T' else 'smaller_rho' if key=='EA_L' else 'larger_parameter'} for key,value in choices.items()}
 token=broker.freeze(choices,ties,frozen_hashes(),code_sha256,frozen_hashes)
 with account.stage_scope('source-calibration',participant=participant,operation='calibration'):
  scal_block=broker.release_scal(token,'final-source-calibration',code_sha256)
  scal,ycal,_=_checked_block(scal_block,20)
  for item in seeds:
   fcal=features(item['model'],scal,forward_charge)
   item['Ts'],item['calibration_status']=temperature(head_logits(fcal,item['source_W'],item['source_b']),ycal,source=True)
   item['source_state_sha256']=state_hash(item['model'])
  hcal=ea_transform(ea,scal_block.corrected_uV.values)
  TsEA,cal=temperature(np.c_[np.zeros(len(hcal)),hcal@coef[:-1]+coef[-1]],ycal,source=True)
  return {'participant':participant,'selected_epoch':selected_epoch,'choices':choices,'neural_sources':seeds,
   'EA_source':ea,'EA_classifier':coef,'EA_Ts':TsEA,'EA_calibration':cal,'EA_source_labels':yf.copy(),'source_refit':False,'freeze_sha256':token}
