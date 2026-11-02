"""Trusted window extraction helpers. No file import side effect.
Real intake must be behind the formal permit; this revision was tested with artificial metadata only.
"""
from contracts import separate_validity,nonempty_group_indices,ValidityStop,Indexed,Block,source_gates
def structural_mapping(groups,container):
 ids=nonempty_group_indices(groups,container)
 return {'selected_group_index':ids[2 if container=='T' else 0],'physical_session':3 if container=='T' else 4,'physical_run':'unknown'}
def extract_partition(run,starts,labels,requested,partition,allowed_labels):
 import numpy as np
 requested=tuple(requested);allowed=set(allowed_labels)
 epoch=[];epoch_ids=[];pre=[];pre_ids=[];ys=[];yids=[];ev=[];pv=[];er=[];pr=[]
 for ordinal in requested:
  cue=int(starts[ordinal])+750
  eok=0<=cue and cue+1125<=len(run.X);pok=partition=='S-fit' and 0<=cue-500 and cue<=len(run.X)
  raw=np.asarray(run.X[cue:cue+1125].T,dtype=np.float64) if eok else None
  precursor=np.asarray(run.X[cue-500:cue].T,dtype=np.float64) if pok else None
  ereason=None if eok else 'epoch_bounds';preason=None if pok else 'precue_bounds_or_not_requested'
  if eok and not np.isfinite(raw).all():eok=False;ereason='epoch_nonfinite'
  if pok and not np.isfinite(precursor).all():pok=False;preason='precue_nonfinite'
  ev.append(bool(eok));pv.append(bool(pok));er.append(ereason);pr.append(preason)
  if eok:
   epoch.append(raw);epoch_ids.append(ordinal)
   if ordinal in allowed:ys.append(int(labels[ordinal])-1);yids.append(ordinal)
  if pok:pre.append(precursor);pre_ids.append(ordinal)
 validity=separate_validity(requested,ev,pv,er,pr)
 return {'raw':Indexed(tuple(epoch_ids),tuple(epoch)),'precue':Indexed(tuple(pre_ids),tuple(pre)),
  'labels':Indexed(tuple(yids),tuple(ys)),'validity':validity}
def preprocess_development(raw_blocks,n_source,n_target):
 """Called inside trusted preprocessing; S-cal is not an input. Freeze Pipeline here."""
 import numpy as np
 from signal_recipe import Pipeline,SignalError
 if set(raw_blocks)!=set(('S-fit','D0','D1','D2')):raise ValidityStop('DEVELOPMENT_PARTITIONS_ONLY')
 fit=raw_blocks['S-fit'];pipe=Pipeline().fit_nuisance(fit['precue'].values,fit['precue'].ordinals)
 corrected={};ids={};failures={}
 for name,raw in raw_blocks.items():
  output=[];valid=[];bad=[]
  for ordinal,x in zip(raw['raw'].ordinals,raw['raw'].values):
   try:output.append(pipe.transform(x));valid.append(ordinal)
   except SignalError as exc:
    if str(exc)!='COMMON_STRUCTURAL_INVALIDITY':raise
    bad.append({'ordinal':ordinal,'reason':str(exc)})
  if not output and name in ('S-fit','D2'):raise ValidityStop('EMPTY_REQUIRED_FIT_OR_SELECTION_PARTITION')
  corrected[name]=np.stack(output) if output else np.empty((0,3,512),dtype=np.float64);ids[name]=tuple(valid);failures[name]=bad
 pipe.fit_scaler(corrected['S-fit'])
 blocks={}
 for name,raw in raw_blocks.items():
  requested=tuple(raw['validity']['ordinals']);labels=dict(zip(raw['labels'].ordinals,raw['labels'].values))
  permitted_ids=tuple(i for i in ids[name] if i in labels)
  blocks[name]=Block(requested,Indexed(ids[name],pipe.neural(corrected[name])),Indexed(ids[name],corrected[name]),
    Indexed(requested,tuple(i in ids[name] for i in requested)),Indexed(permitted_ids,tuple(labels[i] for i in permitted_ids)))
 source_gates(n_source,n_target,ids['S-fit'],list(blocks['S-fit'].labels.values),fit['precue'].ordinals,ids['D2'])
 return pipe,blocks,failures
def generic_schema(groups,container,n_source,n_target,file_identity,participant):
 """No signal/label access: groups contain only onset/sample-count metadata."""
 mapping=structural_mapping(groups,container);group=groups[mapping['selected_group_index']]
 starts=tuple(group['trial_start_samples']);count=n_source if container=='T' else n_target
 if len(starts)!=count or any(b<=a for a,b in zip(starts,starts[1:])):raise ValidityStop('SCHEMA_CHRONOLOGY')
 from science_contract import split
 split_record=split(n_source,n_target);parts=split_record.source if container=='T' else split_record.target
 byid={i:name for name,ids in parts for i in ids};rows=[]
 for i,start in enumerate(starts):
  cue=start+750
  rows.append({'participant':participant,'physical_session':mapping['physical_session'],'physical_run':'unknown','source_identity':file_identity,
   'group_index':mapping['selected_group_index'],'ordinal':i,'trial_start_sample':start,'cue_sample':cue,
   'analysis_interval':(cue,cue+1125),'precue_interval':(cue-500,cue) if byid[i]=='S-fit' else None,'partition':byid[i]})
 return rows
