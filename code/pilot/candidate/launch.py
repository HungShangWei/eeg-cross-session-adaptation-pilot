"""Candidate entry. Exact separate user grant required before science imports.
READY_FOR_EXECUTION_APPROVAL is engineering readiness, never execution permission.
"""
import pathlib,json,sys,os,hashlib,argparse,traceback
C=pathlib.Path(__file__).resolve().parent;PREP=C.parent
TRACEBACK_LIMIT=16384
def fail(message):raise PermissionError(message)
def report_failure(exc):
    # First line keeps the original type/message form; the bounded traceback carries frames only, never locals.
    print(type(exc).__name__+': '+str(exc),file=sys.stderr)
    text=''.join(traceback.format_exception(exc))
    if len(text)>TRACEBACK_LIMIT:text=text[:TRACEBACK_LIMIT//2]+'\n[TRACEBACK TRUNCATED]\n'+text[-TRACEBACK_LIMIT//2:]
    print('--- bounded traceback (no locals) ---\n'+text,file=sys.stderr,end='')
def environment_check():
    import importlib.metadata
    expected=json.loads((C/'config/ENVIRONMENT_METADATA_v1.json').read_text())
    if sys.executable!=expected['executable'] or sys.version!=expected['python'] or sys.prefix!=expected['prefix']:fail('ENVIRONMENT_CHANGED')
    for name,row in expected['packages'].items():
        if 'version' in row and importlib.metadata.version(name)!=row['version']:fail('PACKAGE_VERSION_CHANGED:'+name)
def identity_check(manifest_path):
    raw=pathlib.Path(manifest_path).read_bytes();obj=json.loads(raw)
    listed=[r['path'] for r in obj['files']]
    expected={str(p.relative_to(PREP)) for p in C.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if not listed or len(set(listed))!=len(listed) or not expected.issubset(set(listed)):fail('INCOMPLETE_CANDIDATE_IDENTITY')
    for row in obj['files']:
        original=PREP/row['path'];path=original.resolve()
        if PREP not in path.parents or original.is_symlink():fail('CANDIDATE_PATH')
        b=path.read_bytes()
        if len(b)!=row['bytes'] or hashlib.sha256(b).hexdigest()!=row['sha256']:fail('CANDIDATE_CHANGED')
    return hashlib.sha256(raw).hexdigest()
def worker_environment(run):
    os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='',
        PYTORCH_ENABLE_MPS_FALLBACK='0',TMPDIR=str(run/'tmp'),TMP=str(run/'tmp'),TEMP=str(run/'tmp'),
        MPLCONFIGDIR=str(run/'cache'),XDG_CACHE_HOME=str(run/'cache'),TORCH_HOME=str(run/'cache/torch'))
def install_write_guard(run):
    def write_guard(event,a):
        if event=='open' and a and isinstance(a[0],(str,bytes,os.PathLike)):
            flags=a[2] if len(a)>2 and isinstance(a[2],int) else 0
            if flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                q=pathlib.Path(os.fsdecode(a[0])).absolute().resolve()
                if q!=run and run not in q.parents:fail('WRITE_OUTSIDE_NEW_RUN')
        if event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.symlink','os.link'):
            for value in a[:2 if event in ('os.rename','os.symlink','os.link') else 1]:
                if isinstance(value,(str,bytes,os.PathLike)):
                    q=pathlib.Path(os.fsdecode(value)).absolute().resolve()
                    if q!=run and run not in q.parents:fail('FILESYSTEM_OUTSIDE_NEW_RUN')
        if event in ('socket.connect','socket.bind','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'):fail('OFFLINE_ONLY')
    sys.addaudithook(write_guard)
def worker_startup(run,config,run_id,mode):
    """Shared pre-science startup: write guard, frozen import path, new ledger, initial FORMAL resource check.
    The formal entry calls it only after the exact grant and supervised handoff checks; ENGINEERING_ONLY probes
    call it with their own root and namespace, which grants nothing. A failed initial check closes the ledger.
    """
    install_write_guard(run)
    # Frozen project-module closure precedes third-party environment packages.
    project=str(PREP.parents[1]);sys.path[:]=[str(C/'runtime_modules'),str(C/'frozen'),str(C)]+[x for x in sys.path if x and x not in (project,str(pathlib.Path(project)/'experiments/mi_ops_fixed_tail_v1_1'))]
    from audit_core import Audit
    from resource_guard import ResourceGuard
    audit=Audit(run,run_id,mode)
    try:guard=ResourceGuard(audit,config);guard.check(initial=True);audit.guard=guard.check
    except BaseException:audit.close();raise
    return audit,guard
def main():
    p=argparse.ArgumentParser();p.add_argument('--identity');p.add_argument('--approval');p.add_argument('--run-root');p.add_argument('--supervised-handoff');p.add_argument('--check-unapproved',action='store_true');args=p.parse_args()
    config=json.loads((C/'config/RUN_CONFIG_v1.json').read_text())
    if args.check_unapproved or config['preparation_status']!='READY_FOR_EXECUTION_APPROVAL':fail('EXECUTION_NOT_APPROVED: PREP_BLOCKED')
    if not args.identity or not args.approval or not args.run_root:fail('EXECUTION_NOT_APPROVED: EXACT_GRANT_REQUIRED')
    identity=identity_check(args.identity);approval=json.loads(pathlib.Path(args.approval).read_text())
    required=set(config['authorized_operations_required'])
    if approval.get('resource_policy')!='FORMAL_NORMAL_REQUIRED' or config['formal_resources']['allowed_pressure_codes']!=[1]:fail('FORMAL_REJECTS_PREP_POLICY')
    if approval.get('candidate_identity_sha256')!=identity or approval.get('run_id')!=config['run_id'] or approval.get('approved_by')!='Shang-Wei Hung' or set(approval.get('authorized_operations',[]))!=required:fail('EXECUTION_NOT_APPROVED: GRANT_SCOPE_OR_IDENTITY')
    environment_check()
    run=pathlib.Path(args.run_root)
    if str(run)!=config['run_root'] or run.resolve()!=run:fail('EXACT_RUN_ROOT_REQUIRED')
    handoff=run/'control/parent_launch.json'
    if not args.supervised_handoff or not handoff.exists():fail('SUPERVISED_LAUNCH_REQUIRED')
    hb=handoff.read_bytes();hr=json.loads(hb)
    if hashlib.sha256(hb).hexdigest()!=args.supervised_handoff or hr['parent_pid']!=os.getppid() or hr['candidate_identity_sha256']!=identity:fail('SUPERVISED_HANDOFF_IDENTITY')
    # Readiness is insufficient: the exact separate grant and supervised handoff above are required.
    if not all((run/name).is_dir() for name in ('tmp','cache','control')):fail('SUPERVISOR_ROOT_LAYOUT')
    worker_environment(run)
    audit,guard=worker_startup(run,config,config['run_id'],'NEW_VALIDATION_RUN')
    try:
        audit.event('run_configuration_frozen',candidate_identity_sha256=identity,configuration=config,approval_identity=hashlib.sha256(pathlib.Path(args.approval).read_bytes()).hexdigest())
        from data_service import DataService
        from model_adapter import ModelAdapter
        from flow import execute_core
        service=DataService(json.loads((C/'config/DATA_MANIFEST_v1.json').read_text()),audit)
        adapter=ModelAdapter(audit,identity,config)
        execute_core(service,adapter,audit,identity)
    finally:audit.close()
if __name__=='__main__':
    try:main()
    except BaseException as exc:
        report_failure(exc);raise SystemExit(2)
