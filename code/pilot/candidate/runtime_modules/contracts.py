"""Immutable ordinal/capability contracts. No scientific imports, disk or network side effects."""
from dataclasses import dataclass
import copy,hashlib,json,math,time
# Preparation-stage flags, kept unchanged; no module in this code reads them. Execution status: docs/VALIDATION_SCOPE.md.
FLAGS=dict(non_formal=True,formal_execution_authorized=False,publishable_as_pilot_results=False)
SEEDS=(1103,2207,3301);BUDGETS=(0,5,10,20,40)
class ValidityStop(ValueError):pass
class ResourceStop(RuntimeError):pass
class QuotaStop(RuntimeError):pass
class NumericalFailure(ArithmeticError):pass
class DevelopmentStop(RuntimeError):pass
def digest(obj):
 return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def ordinals(ids):
 ids=tuple(ids)
 if any(type(i) is not int or i<0 for i in ids) or ids!=tuple(sorted(set(ids))):raise ValidityStop('IMMUTABLE_ORDINAL_ORDER')
 return ids
def join_exact(*sequences):
 if not sequences:raise ValidityStop('NO_JOIN')
 ids=ordinals(sequences[0])
 if any(ordinals(x)!=ids for x in sequences[1:]):raise ValidityStop('ORDINAL_JOIN_MISMATCH_NO_REORDER')
 return ids
@dataclass(frozen=True)
class Indexed:
 ordinals:tuple
 values:object
 def __post_init__(self):
  object.__setattr__(self,'ordinals',ordinals(self.ordinals))
  if len(self.values)!=len(self.ordinals):raise ValidityStop('INDEXED_LENGTH')
@dataclass(frozen=True)
class Block:
 requested:tuple
 neural:Indexed
 corrected_uV:Indexed
 epoch_mask:Indexed
 labels:Indexed
 def validate(self,allowed_labels):
  requested=ordinals(self.requested);allowed=set(ordinals(allowed_labels))
  join_exact(requested,self.epoch_mask.ordinals)
  if any(type(v) is not bool for v in self.epoch_mask.values):raise ValidityStop('MASK_TYPE')
  expected=tuple(i for i,v in zip(requested,self.epoch_mask.values) if v)
  join_exact(expected,self.neural.ordinals,self.corrected_uV.ordinals)
  ids=ordinals(self.labels.ordinals)
  if not set(ids)<=allowed or not set(ids)<=set(expected):raise ValidityStop('FORBIDDEN_OR_INVALID_LABEL_ORDINAL')
  if any(type(v) is not int or v not in (0,1) for v in self.labels.values):raise ValidityStop('LABEL_DOMAIN')
  return self
 def labelled_positions(self):
  positions={i:j for j,i in enumerate(self.neural.ordinals)}
  return tuple(positions[i] for i in self.labels.ordinals)
def validate_development(blocks,n_source):
 if set(blocks)!=set(('S-fit','D0','D1','D2')):raise ValidityStop('INITIAL_DEVELOPMENT_FORBIDS_SCAL')
 if not 128<=n_source<=200:raise ValidityStop('SOURCE_COUNT_GATE')
 starts={'S-fit':(0,n_source-80),'D0':(n_source-80,n_source-60),'D1':(n_source-60,n_source-40),'D2':(n_source-40,n_source-20)}
 for name,(lo,hi) in starts.items():
  block=blocks[name]
  if block.requested!=tuple(range(lo,hi)):raise ValidityStop('PARTITION_IDENTITY')
  permitted=tuple(range(lo,min(hi,lo+10))) if name=='D1' else tuple(range(lo,hi))
  block.validate(permitted)
  required=tuple(i for i in block.neural.ordinals if i in permitted)
  if block.labels.ordinals!=required:raise ValidityStop('MISSING_ALLOWED_VALID_LABELS')
 return blocks
def separate_validity(ids,epoch_ok,precue_ok,epoch_reasons,precue_reasons):
 ids=ordinals(ids);n=len(ids)
 if not all(len(a)==n for a in (epoch_ok,precue_ok,epoch_reasons,precue_reasons)):raise ValidityStop('VALIDITY_LENGTH')
 if any(type(v) is not bool for a in (epoch_ok,precue_ok) for v in a):raise ValidityStop('VALIDITY_BOOL')
 for mask,reasons in [(epoch_ok,epoch_reasons),(precue_ok,precue_reasons)]:
  if any((v and reason is not None) or (not v and not reason) for v,reason in zip(mask,reasons)):raise ValidityStop('VALIDITY_REASON')
 return dict(ordinals=ids,epoch_valid=tuple(epoch_ok),precue_valid=tuple(precue_ok),
  epoch_ordinals=tuple(i for i,v in zip(ids,epoch_ok) if v),precue_ordinals=tuple(i for i,v in zip(ids,precue_ok) if v),
  epoch_reasons=tuple(epoch_reasons),precue_reasons=tuple(precue_reasons),no_refill=True)
def source_gates(n_source,n_target,epoch_ids,fit_labels,precue_ids,d2_ids):
 if not 128<=n_source<=200 or not 120<=n_target<=200:raise ValidityStop('PHYSICAL_COUNT_GATE')
 if len(epoch_ids)<48 or len(precue_ids)<20 or len(d2_ids)<10:raise ValidityStop('INDEPENDENT_SOURCE_GATES')
 if len(fit_labels)!=len(epoch_ids) or min(fit_labels.count(0),fit_labels.count(1))<12:raise ValidityStop('SOURCE_CLASS_GATE')
 return True
def nonempty_group_indices(groups,container):
 expected={'T':3,'E':2}
 if container not in expected:raise ValidityStop('CONTAINER')
 ids=tuple(i for i,g in enumerate(groups) if g['trial_count']>0)
 if len(ids)!=expected[container]:raise ValidityStop('PHYSICAL_SESSION_GROUP_COUNT')
 return ids
class StagedSourceBroker:
 """Trusted owner holds S-cal privately; only exported development goes to learner.
 Same-UID process discipline, not an OS security sandbox.
 """
 def __init__(self,development,scal_loader,n_source,identity,event_sink):
  self.__dev=copy.deepcopy(validate_development(development,n_source));self.__scal_loader=scal_loader
  self.n_source=n_source;self.identity=copy.deepcopy(identity);self.sink=event_sink;self.__freeze=None;self.__released=False
 def development(self,recipient):
  self.sink({'event':'development_release','recipient':recipient,'fields':('S-fit','D0','D1','D2'),'identity':self.identity,'monotonic_ns':time.monotonic_ns()})
  return copy.deepcopy(self.__dev)
 def freeze(self,choices,ties,state_hashes,code_hash,current_state_hashes):
  if self.__freeze is not None:raise ValidityStop('FREEZE_ONCE')
  required={'T','H','checkpoint'}
  if set(choices)!=required or set(ties)!=required:raise ValidityStop('FREEZE_COMPLETE_CHOICES_AND_TIES')
  if set(state_hashes)!={str(s) for s in SEEDS} or state_hashes!=current_state_hashes():raise ValidityStop('FREEZE_STATE_IDENTITY')
  for value in [code_hash,*state_hashes.values()]:
   if not isinstance(value,str) or len(value)!=64:raise ValidityStop('FREEZE_HASH_FORMAT')
  payload={'choices':copy.deepcopy(choices),'ties':copy.deepcopy(ties),'state_hashes':copy.deepcopy(state_hashes),'code_hash':code_hash,'input_identity':self.identity}
  token=digest(payload)
  # Event sink must persist successfully before capability becomes available.
  self.sink({'event':'source_choices_frozen','freeze_sha256':token,'payload':payload,'monotonic_ns':time.monotonic_ns()})
  self.__freeze=(token,payload,current_state_hashes)
  return token
 def release_scal(self,token,recipient,code_hash):
  if self.__freeze is None or self.__released:raise PermissionError('SCAL_CAPABILITY_NOT_AVAILABLE')
  expected,payload,current=self.__freeze
  if token!=expected or code_hash!=payload['code_hash'] or current()!=payload['state_hashes'] or digest(payload)!=expected:raise PermissionError('SCAL_FREEZE_IDENTITY_CHANGED')
  self.sink({'event':'scal_release_begin','recipient':recipient,'freeze_sha256':token,'fields':('neural','corrected_uV','labels','ordinals','valid_mask'),'monotonic_ns':time.monotonic_ns()})
  block=self.__scal_loader();requested=tuple(range(self.n_source-20,self.n_source))
  if block.requested!=requested:raise ValidityStop('SCAL_PARTITION')
  block.validate(requested)
  if block.labels.ordinals!=block.neural.ordinals:raise ValidityStop('SCAL_VALID_LABEL_JOIN')
  self.__released=True
  self.sink({'event':'scal_received','recipient':recipient,'freeze_sha256':token,'ordinals':block.labels.ordinals,'monotonic_ns':time.monotonic_ns()})
  return block
def label_usage(events,recipient):
 relevant=[e for e in events if e.get('recipient')==recipient and e.get('partition')=='P']
 closes=[e for e in relevant if e['event']=='label_access_closed']
 if len(closes)!=1:return {'status':'NOT_EVALUABLE','reason':'missing_or_duplicate_label_access_close'}
 acquired=set();used=set()
 for e in relevant:
  if e['event'] not in ('labels_received','labels_used','label_access_closed'):raise ValidityStop('LABEL_EVENT')
  if e['event']!='label_access_closed':
   ids=ordinals(e['ordinals'])
   if any(i>=40 for i in ids):raise ValidityStop('PREFIX_LABEL_EVENT_SCOPE')
   (acquired if e['event']=='labels_received' else used).update(ids)
 if not used<=acquired:raise ValidityStop('USED_WITHOUT_ACQUIRED')
 return {'status':'EVALUATED','acquired':len(acquired),'used':len(used),'no_label_control_eligible':not acquired and not used}
