"""ENGINEERING_ONLY startup probes; never a grant, never a scientific entry, never real data.
They call the same formal functions as launch.main/supervise.main AFTER their grant checks
(install_write_guard, worker_environment, worker_startup, supervisor_startup, worker_env, run_worker)
with roots confined to <candidate parent>/tmp and an ENGINEERING_ONLY namespace. The formal entries still
require the exact identity, grant and handoff; nothing here creates, reads or replaces one.
STOP_POINT: worker_startup has returned (guard, frozen import path, new ledger, initial FORMAL resource check);
the formal 'run_configuration_frozen' event, DataService, ModelAdapter and execute_core are never reached.
Mode library_imports only imports, after STOP_POINT, the modules the formal path loads lazily; nothing is constructed.
"""
import sys,os,json,pathlib,hashlib,time,socket,subprocess,importlib,argparse,fcntl
C=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
import launch
TMP=C.parent/'tmp';NAMESPACE='ENGINEERING_ONLY'
STOP_POINT='after launch.worker_startup returns; before run_configuration_frozen, DataService, ModelAdapter and execute_core'
WRITE=os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND
def scoped(path,must_exist=True):
    run=pathlib.Path(path)
    if not run.is_absolute() or run.resolve()!=run or TMP not in run.parents:raise SystemExit('ENGINEERING_SCOPE')
    if must_exist!=run.exists():raise SystemExit('ENGINEERING_ROOT_STATE')
    return run
def engineering_config(run):
    config=json.loads((C/'config/RUN_CONFIG_v1.json').read_text())
    if str(run)==config['run_root']:raise SystemExit('FORMAL_ROOT_FORBIDDEN')
    return dict(config,run_id='ENGINEERING_ONLY_STARTUP_PROBE',run_root=str(run),namespace=NAMESPACE,formal_execution_authorized=False,preparation_status='ENGINEERING_ONLY_NOT_A_GRANT')
class Recorder:
    """Registered before the formal guard: records write-mode opens, null-device opens and Popen calls.
    With a run root it also marks write-mode opens outside that root, i.e. the ones the guard rejects
    (a library may catch that PermissionError as an OSError, so the rejection would otherwise be silent)."""
    def __init__(self,run=None):self.run=run;self.rows=[];sys.addaudithook(self)
    def __call__(self,event,a):
        if event=='open' and a and isinstance(a[0],(str,bytes,os.PathLike)):
            flags=a[2] if len(a)>2 and isinstance(a[2],int) else 0;path=os.fsdecode(a[0])
            if flags&WRITE or path==os.devnull:
                row={'event':'open','path':path,'flags':flags,'write_flags':bool(flags&WRITE),'O_RDWR':bool(flags&os.O_RDWR)}
                if self.run is not None and flags&WRITE:
                    q=pathlib.Path(path).absolute().resolve();row['outside_run_root']=q!=self.run and self.run not in q.parents
                self.rows.append(row)
        if event=='subprocess.Popen':self.rows.append({'event':'subprocess.Popen','argv':[os.fsdecode(x) for x in a[1]]})
def no_children():
    try:os.waitpid(-1,os.WNOHANG);return False
    except ChildProcessError:return True
def fds_on(path):
    found=[]
    for fd in range(3,512):
        try:p=fcntl.fcntl(fd,fcntl.F_GETPATH,bytes(1024)).split(b'\0',1)[0].decode()
        except OSError:continue
        if p==str(path):found.append(fd)
    return found
def attempt(label,fn,expect):
    try:fn();return {'case':label,'raised':False,'pass':False}
    except BaseException as e:
        return {'case':label,'raised':True,'type':type(e).__name__,'message':str(e)[:512],'pass':expect in str(e)}
class Owner:
    def __init__(self,audit,seconds):self.audit=audit;self.work_end=time.monotonic_ns()+int(seconds*1e9);self.cleanup_end=self.work_end+5_000_000_000;self.rows=[]
    def event(self,**row):self.rows.append(row);self.audit.event('resource_native',detail=row);return True
def native_rows(rows):
    return [{k:r.get(k) for k in ('event','argv','pid','returncode','reaped','complete','stdout_bytes','stderr_bytes','stdout_sha256','primary_error','secondary_errors')} for r in rows]
def helper(run):
    """TEST B: formal write guard installed, then the real native helper runs the three allowlisted queries."""
    run=scoped(run);rec=Recorder();launch.install_write_guard(run)
    from audit_core import Audit,read_events
    import native_helper as nh
    audit=Audit(run,'ENGINEERING_ONLY_HELPER_PROBE',NAMESPACE);owner=Owner(audit,30);calls=[]
    try:
        for argv in (['/usr/bin/vm_stat'],['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'],nh.PS):
            t=time.monotonic();text,pid=nh.native_call(owner,list(argv))
            calls.append({'argv':list(argv),'pid':pid,'elapsed_seconds':time.monotonic()-t,'text_bytes':len(text.encode()),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
                'summary':text.strip() if 'sysctl' in argv[0] else (text.splitlines()[0] if 'vm_stat' in argv[0] else {'rows':len(text.splitlines())})})
        guard_live=attempt('ordinary write outside root while guard live',lambda:open(run.parent/(run.name+'_outside_B.txt'),'w'),'WRITE_OUTSIDE_NEW_RUN')
        guard_live['file_exists_after']=(run.parent/(run.name+'_outside_B.txt')).exists()
    finally:audit.close()
    events=read_events(audit.path)
    out={'test':'B_native_helper_under_installed_formal_guard','namespace':NAMESPACE,'mocks':'none: real write guard, real native_call/NativeIO, real /usr/bin/vm_stat, /usr/sbin/sysctl, /bin/ps',
        'calls':calls,'native_events':native_rows([e['detail'] for e in events if e['event']=='resource_native']),'all_reaped':all(e['detail'].get('reaped') for e in events if e['detail'].get('event')=='native_reaped'),
        'all_returncode_zero':all(e['detail'].get('returncode')==0 for e in events if e['detail'].get('event')=='native_reaped'),'no_children_after':no_children(),
        'recorded_opens_and_popen':rec.rows,'devnull_write_mode_opens':[r for r in rec.rows if r.get('path')==os.devnull and r['write_flags']],
        'devnull_readonly_opens':sum(1 for r in rec.rows if r.get('path')==os.devnull and not r['write_flags']),'guard_live_check':guard_live,'ledger_fds_open_after_close':fds_on(audit.path)}
    out['pass']=len(calls)==3 and out['all_reaped'] and out['all_returncode_zero'] and out['no_children_after'] and not out['devnull_write_mode_opens'] and out['devnull_readonly_opens']==3 and guard_live['pass'] and not guard_live['file_exists_after']
    print(json.dumps(out,indent=1));return 0 if out['pass'] else 1
def negative(run,outside,link):
    """TEST D under the installed formal guard: escapes still rejected, network refused, helper allowlist, timeout and bound reaping."""
    run=scoped(run);outside=pathlib.Path(outside);rec=Recorder();launch.install_write_guard(run)
    from audit_core import Audit,read_events
    import native_helper as nh
    audit=Audit(run,'ENGINEERING_ONLY_NEGATIVE_PROBE',NAMESPACE);cases=[]
    try:
        cases.append(attempt('ordinary write outside root',lambda:open(outside/'d_plain.txt','w'),'WRITE_OUTSIDE_NEW_RUN'))
        cases.append(attempt('os.open /dev/null O_RDWR still rejected (guard not widened)',lambda:os.open(os.devnull,os.O_RDWR),'WRITE_OUTSIDE_NEW_RUN'))
        cases.append(attempt('open /dev/null wb still rejected',lambda:open(os.devnull,'wb'),'WRITE_OUTSIDE_NEW_RUN'))
        cases.append(attempt('subprocess.DEVNULL still rejected before any child',lambda:subprocess.run(['/usr/bin/true'],stdin=subprocess.DEVNULL),'WRITE_OUTSIDE_NEW_RUN'))
        cases.append(attempt('dot-dot path escape',lambda:open(run/'..'/(run.name+'_escape.txt'),'w'),'WRITE_OUTSIDE_NEW_RUN'))
        cases.append(attempt('symlink escape inside root',lambda:open(run/link/'d_via_link.txt','w'),'WRITE_OUTSIDE_NEW_RUN'))
        cases.append(attempt('mkdir outside root',lambda:os.mkdir(outside/'d_newdir'),'FILESYSTEM_OUTSIDE_NEW_RUN'))
        inside=run/'inside.txt';inside.write_text('engineering')
        cases.append(attempt('rename to outside root',lambda:os.rename(inside,outside/'d_moved.txt'),'FILESYSTEM_OUTSIDE_NEW_RUN'))
        cases.append(attempt('symlink creation pointing outside',lambda:os.symlink(outside,run/'d_newlink'),'FILESYSTEM_OUTSIDE_NEW_RUN'))
        cases.append(attempt('getaddrinfo',lambda:socket.getaddrinfo('localhost',80),'OFFLINE_ONLY'))
        def connect():
            s=socket.socket()
            try:s.connect(('127.0.0.1',9))
            finally:s.close()
        cases.append(attempt('socket connect',connect,'OFFLINE_ONLY'))
        before=len(rec.rows)
        for argv in (['/bin/echo','x'],['/usr/bin/vm_stat','-c','1'],['/bin/sh','-c','/usr/bin/vm_stat'],['/usr/bin/curl','http://127.0.0.1']):
            cases.append(attempt('native allowlist '+' '.join(argv),lambda argv=argv:nh.native_call(Owner(audit,30),argv),'NATIVE_ALLOWLIST'))
        cases[-1]['popen_events_during_allowlist_cases']=sum(1 for r in rec.rows[before:] if r['event']=='subprocess.Popen')
        owner=Owner(audit,0.005)
        r=attempt('native timeout with a real allowlisted child (ps)',lambda:nh.native_call(owner,list(nh.PS)),'')
        reaped=[x for x in owner.rows if x.get('event')=='native_reaped']
        r.update(expected_types=['TimeoutExpired','NativeFailure'],native_events=native_rows(owner.rows),
            pass_=r['raised'] and r['type'] in ('TimeoutExpired','NativeFailure') and len(reaped)==1 and reaped[0]['reaped'] and reaped[0]['primary_error'] is not None,no_children_after=no_children())
        r['pass']=r.pop('pass_') and r['no_children_after'];cases.append(r)
        owner=Owner(audit,30);saved=nh.LIMIT;nh.LIMIT=64
        try:r=attempt('native output bound with a real child (vm_stat)',lambda:nh.native_call(owner,['/usr/bin/vm_stat']),'NATIVE_OUTPUT_BOUND')
        finally:nh.LIMIT=saved
        reaped=[x for x in owner.rows if x.get('event')=='native_reaped']
        r.update(native_events=native_rows(owner.rows),no_children_after=no_children());r['pass']=r['pass'] and len(reaped)==1 and reaped[0]['reaped'] and r['no_children_after'];cases.append(r)
    finally:audit.close()
    files=sorted(str(p.relative_to(outside)) for p in outside.rglob('*'))
    allowlist_popen=next(c for c in cases if 'popen_events_during_allowlist_cases' in c)['popen_events_during_allowlist_cases']
    out={'test':'D_negative_regressions_under_formal_guard','namespace':NAMESPACE,'cases':cases,'outside_dir_files_after':files,'allowlist_cases_spawned_children':allowlist_popen,
        'no_children_after':no_children(),'events_chain_valid':bool(read_events(audit.path))}
    out['pass']=all(c['pass'] for c in cases) and files==[] and allowlist_popen==0 and out['no_children_after']
    print(json.dumps(out,indent=1));return 0 if out['pass'] else 1
def startup_failure(run,fault):
    """Formal worker startup with a forced initial-check failure: bounded traceback, ledger closed, own child reaped."""
    run=scoped(run);config=engineering_config(run)
    import native_helper as nh
    if fault=='native_bound':nh.LIMIT=64
    elif fault!='root_symlink':raise SystemExit('FAULT')
    launch.worker_environment(run)
    try:launch.worker_startup(run,config,config['run_id'],'ENGINEERING_ONLY_WORKER_STARTUP_FAILURE')
    except BaseException as exc:
        launch.report_failure(exc)
        from audit_core import read_events
        events=read_events(run/'events.jsonl')
        out={'test':'D_startup_failure_lifecycle','fault':fault,'namespace':NAMESPACE,'exception_type':type(exc).__name__,'exception_message':str(exc),
            'ledger_fds_open_after_failure':fds_on(run/'events.jsonl'),'no_children_after':no_children(),'native_events':native_rows([e['detail'] for e in events if e['event']=='resource_native'])}
        out['pass']=out['ledger_fds_open_after_failure']==[] and out['no_children_after'] and all(e['reaped'] for e in out['native_events'] if e['event']=='native_reaped')
        print(json.dumps(out,indent=1));return 2
    print(json.dumps({'test':'D_startup_failure_lifecycle','fault':fault,'pass':False,'error':'NO_FAILURE'}));return 1
IMPORT_CLOSURE=('numpy','scipy.io','scipy.signal','scipy.optimize','scipy.special','torch','torch.nn','sklearn.covariance','pyriemann.utils.mean',
    'contracts','accounting','operations','array_edges','science_contract','inference_contract','signal_recipe','neural_recipe','ea_recipe',
    'solvers_recipe','numeric_dependencies','trusted_ingress','source_recipe_e3prep','composition','statistics_recipe','scorer','independent_statistics')
def library_imports(run):
    """After the formal worker startup (guard live), import only - never construct or call - the modules the formal
    path loads lazily later, to surface any write-mode open or subprocess a library would attempt under the guard."""
    run=scoped(run);config=engineering_config(run);rec=Recorder(run);launch.worker_environment(run)
    audit,guard=launch.worker_startup(run,config,config['run_id'],'ENGINEERING_ONLY_IMPORT_CLOSURE')
    rows=[]
    try:
        audit.event('ENGINEERING_ONLY_stop_point_reached',stop_point=STOP_POINT,science_entry_reached=False,namespace=NAMESPACE)
        for name in IMPORT_CLOSURE:
            n=len(rec.rows);t=time.monotonic()
            try:m=importlib.import_module(name);row={'module':name,'status':'IMPORTED','file':getattr(m,'__file__',None)}
            except BaseException as e:row={'module':name,'status':'FAILED','type':type(e).__name__,'message':str(e)[:512]}
            row.update(elapsed_seconds=time.monotonic()-t,events_during_import=rec.rows[n:]);rows.append(row)
    finally:audit.close()
    out={'test':'C_import_closure_under_formal_guard','namespace':NAMESPACE,'scope':'module import only after STOP_POINT; no array, model, data service or adapter constructed; no data read',
        'imports':rows,'guard_rejected_write_attempts':[dict(e,module=r['module']) for r in rows for e in r['events_during_import'] if e.get('outside_run_root')],
        'devnull_write_mode_opens':[dict(e,module=r['module']) for r in rows for e in r['events_during_import'] if e.get('path')==os.devnull and e['write_flags']],
        'in_run_root_writes_observed':[dict(e,module=r['module']) for r in rows for e in r['events_during_import'] if e.get('write_flags') and e.get('outside_run_root') is False],
        'library_subprocesses_observed':[dict(e,module=r['module']) for r in rows for e in r['events_during_import'] if e['event']=='subprocess.Popen'],
        'observation_note':'library-internal subprocesses (not the candidate native helper) and writes inside the run root are allowed by the unchanged formal guard; reported, not counted as failures',
        'frozen_paths_inside_candidate':all(C in pathlib.Path(r['file']).resolve().parents for r in rows if r['status']=='IMPORTED' and '.' not in r['module'] and r['module'] not in ('numpy','torch')),
        'versions':{k:getattr(sys.modules.get(k),'__version__',None) for k in ('numpy','scipy','torch','sklearn','pyriemann','matplotlib')},'no_children_after':no_children()}
    out['pass']=all(r['status']=='IMPORTED' for r in rows) and not out['guard_rejected_write_attempts'] and not out['devnull_write_mode_opens'] and out['frozen_paths_inside_candidate'] and out['no_children_after']
    print(json.dumps(out,indent=1));return 0 if out['pass'] else 1
def supervisor(name,fault):
    """TEST C: formal supervisor startup, worker launch/capture/reap and formal worker startup to STOP_POINT."""
    run=scoped(TMP/name,must_exist=False);config=engineering_config(run)
    import supervise
    from audit_core import read_events
    t=time.monotonic()
    try:audit,guard=supervise.supervisor_startup(run,config,config['run_id']+'-supervisor','ENGINEERING_ONLY_SUPERVISOR')
    except BaseException as exc:
        launch.report_failure(exc)
        print(json.dumps({'test':'C_startup_integration','stage':'supervisor_initial_formal_check','exception_type':type(exc).__name__,'exception_message':str(exc),
            'supervisor_events':[e['event'] for e in read_events(run/'control/events.jsonl')]},indent=1));return 3
    try:
        handoff=audit.store_json('parent_launch.json',{'parent_pid':os.getpid(),'candidate_identity_sha256':'ENGINEERING_ONLY_NO_GRANT','run_id':config['run_id'],'namespace':NAMESPACE})
        audit.store_json('ENGINEERING_ONLY_CONFIG.json',config)
    except BaseException:audit.close();raise
    command=[sys.executable,'-B',str(C/'tests/engineering_startup_probe.py'),'worker','--run-root',str(run),'--handoff',handoff['sha256']]+(['--fault',fault] if fault else [])
    failure=supervise.run_worker(run,audit,guard,command,supervise.worker_env(run))
    rows=read_events(run/'control/events.jsonl');stdout=(run/'control/worker.stdout').read_bytes();stderr=(run/'control/worker.stderr').read_bytes()
    try:worker=json.loads(stdout)
    except ValueError:worker=None
    closed=[r for r in rows if r['event']=='worker_closed'][0]
    out={'test':'C_startup_integration' if not fault else 'D_supervised_worker_failure_capture','fault':fault,'namespace':NAMESPACE,'stop_point':STOP_POINT,'engineering_root':str(run),'elapsed_seconds':time.monotonic()-t,
        'supervisor_failure':failure,'worker_closed':{k:closed[k] for k in ('returncode','primary_error','child_reaped','elapsed_seconds')},
        'supervisor_events':[r['event']+(':'+r['detail']['event'] if r['event']=='resource_native' and 'event' in r['detail'] else '') for r in rows],
        'supervisor_initial_sample':[r['detail'] for r in rows if r['event']=='resource_native' and 'A_est_bytes' in r['detail']],
        'worker_stdout_bytes':len(stdout),'worker_stderr_bytes':len(stderr),'worker_stderr_head':stderr.decode(errors='replace')[:400],
        'worker_stderr_has_bounded_traceback':b'--- bounded traceback (no locals) ---' in stderr,'worker':worker,'no_children_after':no_children()}
    if fault:out['pass']=failure is not None and failure['message']=='WORKER_NONZERO' and closed['child_reaped'] and out['worker_stderr_has_bounded_traceback'] and len(stderr)<=launch.TRACEBACK_LIMIT+4096 and worker is not None and worker.get('pass')
    else:out['pass']=failure is None and closed['returncode']==0 and closed['child_reaped'] and worker is not None and worker.get('pass') and out['no_children_after']
    print(json.dumps(out,indent=1));return 0 if out['pass'] else 4
def worker(run,handoff,fault):
    """Spawned by run_worker. Mirrors launch.main after its grant checks, then stops at STOP_POINT."""
    run=scoped(run)
    if not all((run/n).is_dir() for n in ('tmp','cache','control')):raise SystemExit('SUPERVISOR_ROOT_LAYOUT')
    hb=(run/'control/parent_launch.json').read_bytes();hr=json.loads(hb)
    if hashlib.sha256(hb).hexdigest()!=handoff or hr['parent_pid']!=os.getppid() or hr['namespace']!=NAMESPACE:raise SystemExit('ENGINEERING_HANDOFF')
    config=json.loads((run/'control/ENGINEERING_ONLY_CONFIG.json').read_text())
    if config['namespace']!=NAMESPACE or config['run_root']!=str(run) or config['formal_execution_authorized'] is not False:raise SystemExit('ENGINEERING_CONFIG')
    if fault:return startup_failure(str(run),fault)
    rec=Recorder();launch.worker_environment(run)
    audit,guard=launch.worker_startup(run,config,config['run_id'],'ENGINEERING_ONLY_WORKER')
    from audit_core import read_events
    try:
        audit.event('ENGINEERING_ONLY_stop_point_reached',stop_point=STOP_POINT,science_entry_reached=False,namespace=NAMESPACE)
        modules={}
        for name in ('data_service','model_adapter','flow'):
            m=importlib.import_module(name);modules[name]=str(pathlib.Path(m.__file__).resolve().relative_to(C))
        guard_live=attempt('ordinary write outside root while guard live',lambda:open(run.parent/(run.name+'_outside_C.txt'),'w'),'WRITE_OUTSIDE_NEW_RUN')
        guard_live['file_exists_after']=(run.parent/(run.name+'_outside_C.txt')).exists()
    finally:audit.close()
    rows=read_events(run/'events.jsonl');detail=[r['detail'] for r in rows if r['event']=='resource_native']
    out={'role':'worker','namespace':NAMESPACE,'stop_point_reached':rows[-1]['event']=='ENGINEERING_ONLY_stop_point_reached','science_entry_reached':False,
        'worker_events':[r['event']+(':'+r['detail']['event'] if r['event']=='resource_native' and 'event' in r['detail'] else '') for r in rows],
        'native_events':native_rows([d for d in detail if 'event' in d]),'initial_formal_sample':[d for d in detail if 'A_est_bytes' in d],
        'module_level_imports_only_no_construction':modules,'guard_live_check':guard_live,'recorded_opens_and_popen':rec.rows,
        'devnull_write_mode_opens':[r for r in rec.rows if r.get('path')==os.devnull and r['write_flags']],'ledger_fds_open_after_close':fds_on(run/'events.jsonl'),
        'data_service_constructed':False,'model_adapter_constructed':False,'execute_core_called':False,'no_children_after':no_children(),
        'environment':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','TMPDIR','PYTORCH_ENABLE_MPS_FALLBACK','CUDA_VISIBLE_DEVICES')}}
    reaped=[d for d in detail if d.get('event')=='native_reaped']
    out['pass']=out['stop_point_reached'] and len(reaped)==3 and all(d['reaped'] and d['returncode']==0 for d in reaped) and len(out['initial_formal_sample'])==1 and not out['devnull_write_mode_opens'] and guard_live['pass'] and not guard_live['file_exists_after'] and out['ledger_fds_open_after_close']==[] and out['no_children_after']
    print(json.dumps(out,indent=1));return 0 if out['pass'] else 1
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('helper','negative','startup_failure','library_imports','supervisor','worker'));ap.add_argument('--run-root');ap.add_argument('--name')
    ap.add_argument('--outside');ap.add_argument('--link');ap.add_argument('--handoff');ap.add_argument('--fault');a=ap.parse_args()
    try:
        if a.mode=='helper':code=helper(a.run_root)
        elif a.mode=='negative':code=negative(a.run_root,a.outside,a.link)
        elif a.mode=='startup_failure':code=startup_failure(a.run_root,a.fault)
        elif a.mode=='library_imports':code=library_imports(a.run_root)
        elif a.mode=='supervisor':code=supervisor(a.name,a.fault)
        else:code=worker(a.run_root,a.handoff,a.fault)
    except BaseException as exc:
        launch.report_failure(exc);code=2
    raise SystemExit(code)
