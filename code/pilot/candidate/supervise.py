"""New-run bounded supervisor and formal entry point; it was not executed during preparation (PREP).
Readiness alone never creates FUTURE_RUN_ROOT; a separate exact grant is required.
Execution status is documented in docs/VALIDATION_SCOPE.md.
"""
import os,sys,json,pathlib,time,subprocess,signal,hashlib,argparse
from launch import identity_check,environment_check,C,PREP,fail,report_failure
def supervisor_startup(run,config,run_id,mode):
    """Shared supervisor startup after the grant checks: new root layout, supervisor ledger, initial FORMAL check.
    ENGINEERING_ONLY probes reuse it with their own root and namespace. A failed initial check closes the ledger.
    """
    run.mkdir(parents=True,exist_ok=False)
    for name in ('tmp','cache','control'):(run/name).mkdir()
    from audit_core import Audit
    from resource_guard import ResourceGuard
    audit=Audit(run/'control',run_id,mode)
    try:guard=ResourceGuard(audit,config);guard.check(initial=True)
    except BaseException:audit.close();raise
    return audit,guard
def worker_env(run):
    env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='',PYTORCH_ENABLE_MPS_FALLBACK='0',TMPDIR=str(run/'tmp'),TMP=str(run/'tmp'),TEMP=str(run/'tmp'),MPLCONFIGDIR=str(run/'cache'),XDG_CACHE_HOME=str(run/'cache'),TORCH_HOME=str(run/'cache/torch'))
    env.pop('PYTHONPATH',None);return env
def run_worker(run,audit,guard,command,env):
    """Launch, capture, bound and reap the one owned worker, then close the supervisor ledger.
    Shared by the formal supervisor and ENGINEERING_ONLY probes; returns the primary failure or None.
    """
    child=None;failure=None;code=None
    out=run/'control/worker.stdout';err=run/'control/worker.stderr';start=time.monotonic()
    try:
        with out.open('xb') as fo,err.open('xb') as fe:
            child=subprocess.Popen(command,cwd=run,env=env,stdout=fo,stderr=fe,start_new_session=True)
            audit.event('worker_started',pid=child.pid,command=command,owned_process_group_by_launch_contract=child.pid)
            while child.poll() is None:
                guard.check()
                if time.monotonic()-start>=3540:raise TimeoutError('RUN_TIME_CAP_CLEANUP_RESERVED')
                if out.stat().st_size+err.stat().st_size>8*1048576:raise RuntimeError('CAPTURE_SIZE_CAP')
                time.sleep(.2)
            code=child.wait(timeout=1)
            if code!=0:raise RuntimeError('WORKER_NONZERO')
    except BaseException as exc:failure={'type':type(exc).__name__,'message':str(exc)}
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
        audit.event('worker_closed',returncode=None if child is None else child.returncode,primary_error=failure,
            elapsed_seconds=time.monotonic()-start,child_reaped=child is None or child.poll() is not None,
            cleanup_scope='owned Popen child/group; no historical job or borrowed PID touched')
        audit.close()
    return failure
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--identity',required=True);ap.add_argument('--approval',required=True);ap.add_argument('--run-root',required=True);args=ap.parse_args()
    config=json.loads((C/'config/RUN_CONFIG_v1.json').read_text())
    if config['preparation_status']!='READY_FOR_EXECUTION_APPROVAL':fail('EXECUTION_NOT_APPROVED: PREP_BLOCKED')
    identity=identity_check(args.identity);approval=json.loads(pathlib.Path(args.approval).read_text())
    required=set(config['authorized_operations_required'])
    if approval.get('resource_policy')!='FORMAL_NORMAL_REQUIRED' or config['formal_resources']['allowed_pressure_codes']!=[1]:fail('FORMAL_REJECTS_PREP_POLICY')
    if approval.get('candidate_identity_sha256')!=identity or approval.get('run_id')!=config['run_id'] or approval.get('approved_by')!='Shang-Wei Hung' or set(approval.get('authorized_operations',[]))!=required:fail('EXECUTION_NOT_APPROVED')
    environment_check()
    run=pathlib.Path(args.run_root)
    if str(run)!=config['run_root'] or run.exists() or run.resolve()!=run:fail('NEW_RUN_ROOT_REQUIRED')
    audit,guard=supervisor_startup(run,config,config['run_id']+'-supervisor','NEW_VALIDATION_RUN_SUPERVISOR')
    try:handoff=audit.store_json('parent_launch.json',{'parent_pid':os.getpid(),'candidate_identity_sha256':identity,'run_id':config['run_id']})
    except BaseException:audit.close();raise
    command=[sys.executable,'-B',str(C/'launch.py'),'--identity',args.identity,'--approval',args.approval,'--run-root',str(run),'--supervised-handoff',handoff['sha256']]
    failure=run_worker(run,audit,guard,command,worker_env(run))
    if failure:raise RuntimeError(json.dumps(failure))
if __name__=='__main__':
    try:main()
    except BaseException as exc:report_failure(exc);raise SystemExit(2)
