"""E1-A/1.1 + OPS01: immutable split and information contracts. E2 only."""
from dataclasses import dataclass
import hashlib,json
# Preparation-stage flags, kept unchanged; no module in this code reads them. Execution status: docs/VALIDATION_SCOPE.md.
FLAGS={"non_formal":True,"formal_execution_authorized":False,"publishable_as_pilot_results":False}
PROTOCOL_SHA256="0992e97e45b9565ffbe11457237e1b756e8ea5b384aaf0f4a31ffdbe509db78f"
OPS01_SHA256="c863dcf377fef1009ff31cb198565e03c055a660aee78ef4e62e845dd937db91"
F=40; BUDGETS=(0,5,10,20,40); PRIMARY_D=10; SEED_BASES=(1103,2207,3301)
class ContractError(ValueError):pass
@dataclass(frozen=True)
class Split:
 source:tuple
 target:tuple
 n_source:int
 n_target:int
 def part(self,name):
  for k,v in self.source+self.target:
   if k==name:return v
  raise ContractError("UNKNOWN_PARTITION")
def split(n_source,n_target):
 if not 128<=n_source<=200 or not 120<=n_target<=200:raise ContractError("COUNT_GATE")
 ranges=(("S-fit",0,n_source-80),("D0",n_source-80,n_source-60),("D1",n_source-60,n_source-40),("D2",n_source-40,n_source-20),("S-cal",n_source-20,n_source))
 return Split(tuple((k,tuple(range(a,b))) for k,a,b in ranges),(("P",tuple(range(40))),("Q",tuple(range(40,n_target)))),n_source,n_target)
def first_d(d,valid):
 if d not in BUDGETS or len(valid)!=F:raise ContractError("PREFIX_CONTRACT")
 return tuple(i for i in range(d) if bool(valid[i])) # no replacement of invalid ordinals
def real_smoke_ids(s):
 return {k:(s.part(k)[:32] if k=="S-fit" else s.part(k)) for k in ("S-fit","D0","D1","D2")}
def formal_entry(*args,**kwargs):raise PermissionError("E3_NOT_AUTHORIZED")
def real_access(participant,physical_session,partition,action):
 if participant not in (1,2) or physical_session!=3 or partition not in ("S-fit","D0","D1","D2"):
  raise PermissionError("REAL_E2_ACCESS_DENIED")
 if action not in ("source_smoke","structure"):raise PermissionError("ACTION_DENIED")
def interval_disjoint(records):
 """records=(run_id, partition, start, end); reject cross-partition sample overlap."""
 for j,(r,p,a,b) in enumerate(records):
  if not 0<=a<b:raise ContractError("INTERVAL")
  for r_next,p2,c,d in records[j+1:]:
   if r==r_next and p!=p2 and max(a,c)<min(b,d):raise ContractError("CROSS_PARTITION_BUFFER")
 return True
def digest_json(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
class SyntheticLabelBroker:
 """In-memory artificial labels only; never accepts a real MAT label array."""
 def __init__(self,labels,fixture_id):
  if not fixture_id.startswith("synthetic-"):raise ContractError("SYNTHETIC_ONLY")
  self.__labels=tuple(int(x) for x in labels);self.access=[]
  if not all(x in (0,1) for x in self.__labels):raise ContractError("LABEL_DOMAIN")
 def prefix(self,d,valid):
  ids=first_d(d,valid);self.access.append({"requested":d,"inspected":len(ids),"ordinals":ids})
  return ids,tuple(self.__labels[i] for i in ids)
 def final(self,*args,**kwargs):raise PermissionError("BROKER_HAS_NO_FINAL_LABEL_API")
