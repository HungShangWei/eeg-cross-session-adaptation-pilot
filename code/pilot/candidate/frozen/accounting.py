"""Typed primitive receipts; no implicit grant, numeric cache, retry or refund.
Preparation-stage flag note (non_formal=true; formal_execution_authorized=false;
publishable_as_pilot_results=false) predates the reported execution; see docs/VALIDATION_SCOPE.md.
Reserve and lease callbacks are provided by the authorized adapter, never by the core.
"""
import copy,time
from contracts import digest,QuotaStop,ValidityStop
KINDS=('T_grid','H_optimizer','EA_optimizer','Riemannian_reference','OAS_fit','forward','optimizer_step','native_alignment','native_eigen')
class CallAccount:
 def __init__(self,reserve,sink,lease,code_sha256,context):
  if not all(callable(x) for x in (reserve,sink,lease)) or len(code_sha256)!=64:raise PermissionError('ACCOUNT_CAPABILITY_REQUIRED')
  self.reserve=reserve;self.sink=sink;self.lease=lease;self.code=code_sha256;self.context=copy.deepcopy(context);self.sequence=0
 def __deepcopy__(self,memo):return self # shared audit sink only; no numeric state/cache
 def run(self,kind,input_identity,fn):
  if kind not in KINDS:raise ValidityStop('UNKNOWN_PRIMITIVE')
  self.lease();self.sequence+=1
  key=digest(dict(code=self.code,context=self.context,sequence=self.sequence,kind=kind,input=input_identity))
  base=dict(call_id=key,kind=kind,input_identity=copy.deepcopy(input_identity),context=copy.deepcopy(self.context),code_sha256=self.code)
  self.sink(dict(base,event='attempt',monotonic_ns=time.monotonic_ns()))
  self.reserve(kind,key) # consumed before action; stopped/failed attempts never refunded
  start=time.monotonic_ns();entered=False
  try:
   self.lease()
   self.sink(dict(base,event='primitive_enter',monotonic_ns=start));entered=True
   result=fn()
   status=result[-1] if isinstance(result,tuple) and result and isinstance(result[-1],dict) else {}
   detail={k:status[k] for k in ('status','active','fallback','iterations','evaluations','gradient_evaluations','final_gradient_norm','final_gradient_source') if k in status}
   self.sink(dict(base,event='primitive_return',elapsed_ns=time.monotonic_ns()-start,entered=True,detail=detail))
   return result
  except BaseException as exc:
   # Preserve the primary mandatory stop even if recording also fails.
   try:self.sink(dict(base,event='primitive_stop',elapsed_ns=time.monotonic_ns()-start,entered=entered,error_type=type(exc).__name__,reason=str(exc)[:256]))
   except BaseException:pass
   raise
 def skipped(self,kind,input_identity,fn):
  self.lease();self.sequence+=1
  key=digest(dict(code=self.code,context=self.context,sequence=self.sequence,kind=kind,input=input_identity))
  result=fn()
  self.sink(dict(event='primitive_skipped',call_id=key,kind=kind,input_identity=input_identity,entered=False,charged_units=0,reason='ineligible_by_unchanged_recipe',monotonic_ns=time.monotonic_ns()))
  return result
 def alias(self,row,original_receipt):
  self.lease();self.sink(dict(event='alias_reuse',row=row,original_receipt=original_receipt,marginal_primitive_calls=0,code_sha256=self.code))
def array_identity(value):
 import numpy as np,hashlib
 a=np.asarray(value)
 if a.dtype.hasobject:raise ValidityStop('OBJECT_ARRAY_IDENTITY')
 return dict(shape=list(a.shape),dtype=str(a.dtype),sha256=hashlib.sha256(a.tobytes(order='C')).hexdigest())
