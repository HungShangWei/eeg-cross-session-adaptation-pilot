"""Bounded owned native helpers; inherited process group is a launch contract, not an observation."""
import os,time,subprocess,selectors,uuid,hashlib
PS=['/bin/ps','-axo','pid=,ppid=,pgid=,lstart=,rss=,state=']
NATIVE={tuple(PS),('/usr/bin/vm_stat',),('/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level')}
LIMIT=1048576
class NativeFailure(RuntimeError):pass
class NativeIO:
 def now(self):return time.monotonic_ns()
 def own_group(self):return os.getpgid(os.getpid())
 def spawn(self,argv):
  # subprocess.DEVNULL opens os.devnull O_RDWR, which the formal write guard rejects outside the run root.
  # An explicit read-only null file keeps the same empty EOF stdin without widening that guard.
  with open(os.devnull,'rb',buffering=0) as null:
   return subprocess.Popen(argv,shell=False,env=dict(os.environ,LC_ALL='C',LANG='C'),stdin=null,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def exchange(self,p,end,limit):
  chunks={'stdout':bytearray(),'stderr':bytearray()};seen=0;sel=selectors.DefaultSelector()
  try:
   for key in chunks:
    pipe=getattr(p,key);os.set_blocking(pipe.fileno(),False);sel.register(pipe,selectors.EVENT_READ,key)
   while sel.get_map():
    left=(end-self.now())/1e9
    if left<=0:raise subprocess.TimeoutExpired(p.args,.8)
    for key,_ in sel.select(min(left,.02)):
     b=os.read(key.fileobj.fileno(),min(65536,limit-seen+1))
     if not b:sel.unregister(key.fileobj);continue
     seen+=len(b)
     if seen>limit:raise NativeFailure('NATIVE_OUTPUT_BOUND')
     chunks[key.data].extend(b)
   left=(end-self.now())/1e9
   if left<=0:raise subprocess.TimeoutExpired(p.args,.8)
   # Both pipes reached EOF through the bounded reader; communicate only reaps/reads empty tails.
   tail=p.communicate(timeout=left)
   for key,b in zip(chunks,tail):
    b=b or b'';seen+=len(b)
    if seen>limit:raise NativeFailure('NATIVE_OUTPUT_BOUND')
    chunks[key].extend(b)
   return bytes(chunks['stdout']),bytes(chunks['stderr'])
  finally:sel.close()
 def reap(self,p,deadline):
  errors=[]
  # Popen poll/wait owns this child. Never signal a process group or a borrowed PID.
  try:
   if p.poll() is None:
    try:p.kill()
    except ProcessLookupError:
     if p.poll() is None:raise
   left=(deadline-self.now())/1e9
   if left<=0:
    if p.poll() is None:raise NativeFailure('HELPER_CLEANUP_DEADLINE')
   else:p.wait(timeout=left)
  except BaseException as e:errors.append({'type':type(e).__name__,'message':str(e)[:512]})
  finally:
   for name in ('stdin','stdout','stderr'):
    pipe=getattr(p,name,None)
    if pipe:
     try:pipe.close()
     except BaseException as e:errors.append({'type':type(e).__name__,'message':str(e)[:512]})
  return {'returncode':p.returncode,'reaped':p.poll() is not None,'errors':errors}
def native_call(owner,argv,cleanup=False,*,io=None):
 io=io or NativeIO()
 if tuple(argv) not in NATIVE:raise NativeFailure('NATIVE_ALLOWLIST')
 outer=owner.cleanup_end if cleanup else owner.work_end
 started=io.now();end=min(outer,started+800000000)
 if end<=started:raise NativeFailure('NATIVE_DEADLINE')
 parent_group=io.own_group();p=None;out=err=b'';primary=None;secondary=[];complete=False;reap=None
 helper_id=uuid.uuid4().hex
 try:
  p=io.spawn(argv)
  if not owner.event(event='native_start',helper_id=helper_id,argv=argv,pid=p.pid,ppid=os.getpid(),
     started_ns=started,expected_inherited_pgid=parent_group,pgid_observed=None,
     group_identity_source='inherited-by-launch-contract; child pgid NOT_OBSERVED',
     ownership_source='direct Popen child',deadline_ns=end):
   raise NativeFailure('NATIVE_START_LOG_FAILURE')
  out,err=io.exchange(p,end,LIMIT)
  if len(out)+len(err)>LIMIT:raise NativeFailure('NATIVE_OUTPUT_BOUND')
  complete=True
  sink=getattr(owner,'native_output_sink',None)
  if sink is not None:sink(helper_id,out,err)
  if io.now()>end:raise NativeFailure('NATIVE_DEADLINE')
  if p.returncode!=0:raise NativeFailure('NATIVE_EXIT_NONZERO:'+str(p.returncode))
  text=out.decode('utf-8',errors='strict')
 except BaseException as e:primary=e
 finally:
  if p is not None:
   try:reap=io.reap(p,owner.cleanup_end)
   except BaseException as e:reap={'reaped':False,'returncode':p.returncode,'errors':[{'type':type(e).__name__,'message':str(e)[:512]}]}
   secondary.extend(reap['errors'])
   record={'event':'native_reaped','helper_id':helper_id,'pid':p.pid,'returncode':p.returncode,
    'reaped':reap['reaped'],'complete':complete,'stdout_bytes':len(out),'stderr_bytes':len(err),
    'stdout_sha256':hashlib.sha256(out).hexdigest(),'stderr_sha256':hashlib.sha256(err).hexdigest(),
    'pgid_observed':None,'ended_ns':io.now(),'primary_error':None if primary is None else {'type':type(primary).__name__,'message':str(primary)[:512]},
    'secondary_errors':secondary}
   # Fixed allowlisted system outputs only; parsed samples also retain their own raw evidence.
   if complete and len(out)+len(err)<=16384:record.update(stdout_raw=out.decode(errors='replace'),stderr_raw=err.decode(errors='replace'))
   try:
    if not owner.event(**record):secondary.append({'type':'LogFailure','message':'NATIVE_END_LOG_FAILURE'})
   except BaseException as e:secondary.append({'type':type(e).__name__,'message':str(e)[:512]})
   if primary is None and (secondary or not reap['reaped']):primary=NativeFailure('NATIVE_CLEANUP_OR_END_LOG')
 if primary is not None:
  try:primary.native_secondary_errors=secondary
  except Exception:pass
  raise primary
 return text,p.pid
class NativeMixin:
 def native(self,argv,cleanup=False):return native_call(self,argv,cleanup)
