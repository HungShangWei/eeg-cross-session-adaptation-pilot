"""B2-R candidate durable boundaries. Standard library only; no scientific entry.
Scientific execution requires a separately approved, identity-bound grant.
"""
import os,json,hashlib,pathlib,math,contextlib,copy,time
class BoundaryError(RuntimeError):pass
def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha_file(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()
def checked(root,path):
    root=pathlib.Path(root);p=pathlib.Path(path)
    if not root.is_absolute() or not p.is_absolute() or (p!=root and root not in p.parents):raise BoundaryError('WRITE_SCOPE')
    if root.resolve()!=root or p.resolve()!=p or any(x.is_symlink() for x in (p,*p.parents)):raise BoundaryError('SYMLINK_OR_PATH')
    return p
def ordinals(values):
    v=list(values)
    if any(type(x)!=int or x<0 for x in v) or v!=sorted(set(v)):raise BoundaryError('ORDINAL_ORDER_OR_DUPLICATE')
    return v
def verify_state_file(root,artifact):
    record=artifact.get('record')
    if not isinstance(record,dict):raise BoundaryError('STATE_ARTIFACT_REQUIRED')
    p=checked(root,pathlib.Path(record['path']))
    if p.stat().st_size!=record['bytes'] or sha_file(p)!=record['sha256']:raise BoundaryError('STATE_RECORD_CHANGED')
    obj=json.loads(p.read_text());archive=obj.get('archive')
    if archive is not None:
        q=checked(root,pathlib.Path(archive['path']))
        if q.stat().st_size!=archive['bytes'] or sha_file(q)!=archive['sha256']:raise BoundaryError('STATE_ARCHIVE_CHANGED')
    if artifact.get('payload_identity') is not None and digest(obj['payload'])!=artifact['payload_identity']:raise BoundaryError('STATE_PAYLOAD_CHANGED')
    return True
class Audit:
    def __init__(self,root,run_id,mode,guard=lambda:None):
        self.root=pathlib.Path(root);self.run_id=run_id;self.mode=mode;self.guard=guard
        self.sequence=0;self.head='0'*64;self.poisoned=False
        self.path=checked(self.root,self.root/'events.jsonl')
        if self.path.exists():raise BoundaryError('NEW_LEDGER_ONLY')
        self.fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_APPEND|getattr(os,'O_NOFOLLOW',0),0o600)
    def event(self,event,parent=None,**fields):
        if self.poisoned:raise BoundaryError('AUDIT_POISONED')
        self.guard();row={'run_id':self.run_id,'mode':self.mode,'process_id':os.getpid(),'process_sequence':self.sequence+1,
            'previous_event_sha256':self.head,'parent_event_id':parent,'event':event,**fields}
        row['event_id']=digest(row);raw=(json.dumps(row,sort_keys=True,allow_nan=False)+'\n').encode()
        if len(raw)>1048576:raise BoundaryError('EVENT_SIZE')
        try:
            if os.write(self.fd,raw)!=len(raw):raise OSError('SHORT_EVENT_WRITE')
            os.fsync(self.fd)
        except BaseException:
            self.poisoned=True;raise
        self.sequence+=1;self.head=row['event_id'];return row['event_id']
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
    @contextlib.contextmanager
    def boundary(self,event,**fields):
        entered=self.event(event+'_enter',**fields)
        result={}
        try:
            yield result
        except BaseException as exc:
            self.event(event+'_abort',parent=entered,error_type=type(exc).__name__,completed=False)
            raise
        else:self.event(event+'_return',parent=entered,completed=True,**result)
    def store_json(self,name,obj):
        p=checked(self.root,self.root/name);p.parent.mkdir(parents=True,exist_ok=True)
        raw=(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n').encode();self.guard()
        with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def read_events(path):
    raw=pathlib.Path(path).read_bytes()
    if not raw.endswith(b'\n'):raise BoundaryError('TRUNCATED_AUDIT')
    rows=[];head='0'*64
    for seq,line in enumerate(raw.splitlines(),1):
        r=json.loads(line);eid=r.pop('event_id')
        if r['process_sequence']!=seq or r['previous_event_sha256']!=head or digest(r)!=eid:raise BoundaryError('AUDIT_CHAIN')
        r['event_id']=eid;rows.append(r);head=eid
    return rows
class Feedback:
    """Persist actual provider reply before exposing its view to a recipient.
    This is a same-process API boundary, not an OS security claim.
    """
    def __init__(self,audit,container_by_person):
        self.audit=audit;self.containers=container_by_person;self.open={};self.acquired=set();self.counter=0
    def request(self,person,seed,method,budget=10):
        if person not in range(1,10) or seed not in (1103,2207,3301) or method not in ('T','H') or budget!=10:raise BoundaryError('RECIPIENT_SCOPE')
        recipient=f'{person}:{seed}:{method}:10'
        if recipient in self.open:raise BoundaryError('RECIPIENT_REPLAY')
        self.counter+=1;call=f'{self.audit.run_id}:prefix:{self.counter}'
        request={'person':person,'recipient':recipient,'call_id':call,'physical_session':4,'budget':10,
            'container_sha256':self.containers[person],'requested_ordinals':list(range(10))}
        parent=self.audit.event('prefix_request',**request)
        self.open[recipient]={'request':request,'parent':parent,'received':False,'used':False,'ended':False}
        return copy.deepcopy(request)
    def receive(self,request,reply,view_identity):
        key=request['recipient'];st=self.open.get(key)
        if st is None or st['request']!=request or st['received'] or st['ended']:raise BoundaryError('RECEIPT_STATE')
        for k in ('person','recipient','call_id','physical_session','budget','container_sha256','requested_ordinals'):
            if reply.get(k)!=request[k]:raise BoundaryError('RECEIPT_'+k.upper())
        mask=reply.get('valid');ids=ordinals(reply.get('label_ordinals',[]))
        if not isinstance(mask,list) or len(mask)!=10 or any(type(x)!=bool for x in mask):raise BoundaryError('VALID_MASK')
        if ids!=[i for i,v in enumerate(mask) if v]:raise BoundaryError('LEGAL_VALID_LABEL_JOIN')
        if view_identity.get('requested')!=list(range(10)) or view_identity.get('ordinals')!=ids or view_identity.get('label_ordinals')!=ids or view_identity.get('valid')!=mask:
            raise BoundaryError('VIEW_RECEIPT_ORDINAL_BINDING')
        onset=reply.get('sample_onset_indices')
        if not isinstance(onset,list) or len(onset)!=10 or any(type(x)!=int or x<0 for x in onset):raise BoundaryError('ONSET_METADATA')
        binding={'container_sha256':request['container_sha256'],'physical_session':4,'ordinals':ids,
                 'sample_onset_indices':onset,'valid':mask,'view_identity':view_identity}
        new=[]
        for i in ids:
            unit=(request['person'],request['container_sha256'],4,i)
            if unit not in self.acquired:self.acquired.add(unit);new.append(i)
        event=self.audit.event('labels_received',parent=st['parent'],**request,legal_binding=binding,new_unique_ordinals=new)
        st.update(received=True,binding=binding,receive_event=event)
        return event
    def use(self,recipient,call_id,purpose,input_identity):
        st=self.open.get(recipient)
        if st is None or not st['received'] or st['ended'] or st['request']['call_id']!=call_id:raise BoundaryError('USE_WITHOUT_EXACT_RECEIPT')
        if purpose not in ('schema_validation','class_gate','optimizer','solver_fallback_eligibility'):raise BoundaryError('USE_PURPOSE')
        e=self.audit.event('labels_used',parent=st['receive_event'],recipient=recipient,call_id=call_id,
            purpose=purpose,legal_binding_sha256=digest(st['binding']),input_identity=input_identity)
        st['used']=True;return e
    def end(self,recipient,call_id,status,parent=None):
        st=self.open.get(recipient)
        if st is None or st['ended'] or st['request']['call_id']!=call_id:raise BoundaryError('END_IDENTITY')
        success=status in ('completed','protocol_fallback')
        if success and (not st['received'] or not st['used']):raise BoundaryError('END_BEFORE_USE')
        e=self.audit.event('label_access_ended',parent=parent or st['parent'],recipient=recipient,call_id=call_id,
                           status=status,completed=success,successful_close=success)
        st['ended']=True;st['successful_close']=success;return e
def state_change(method,before,after):
    allowed={'temperature','status'} if method=='T' else {'head_W','head_b','status'} if method=='H' else None
    if allowed is None or set(before)!=set(after):raise BoundaryError('STATE_SCHEMA')
    changed=[k for k in before if before[k]!=after[k]]
    bad=sorted(set(changed)-allowed)
    if bad:raise BoundaryError('FORBIDDEN_STATE_CHANGE:'+','.join(bad))
    return {'changed':sorted(changed),'frozen_keys_checked':sorted(set(before)-allowed)}
class Cohort:
    def __init__(self,audit,expected_q,code_identity):
        self.audit=audit;self.expected_q={int(p):ordinals(q) for p,q in expected_q.items()}
        self.code_identity=code_identity;self.rows={};self.seal=None
        self.expected={f'{p}:{s}:{m}:10' for p in range(1,10) for s in (1103,2207,3301) for m in ('T','H')}
        self.audit.event('cohort_planned',instances=sorted(self.expected),independent_n=9)
    def add(self,row):
        ref=row['ref']
        if ref not in self.expected or ref in self.rows:raise BoundaryError('COHORT_DUPLICATE_OR_UNEXPECTED')
        p=int(ref.split(':')[0]);q=self.expected_q[p]
        if row['ordinals']!=q or row['denominator']!=len(q):raise BoundaryError('Q_ORDER_OR_DENOMINATOR')
        v=row['valid']
        if len(v)!=len(q) or any(type(x)!=bool for x in v):raise BoundaryError('Q_VALID_SCHEMA')
        if row['outcome'] not in ('completed','protocol_fallback'):raise BoundaryError('ENGINEERING_FAILURE_NOT_FALLBACK')
        fit=row.get('fit_status',{});fallback=row['outcome']=='protocol_fallback'
        if fit.get('active') is not (not fallback) or fit.get('fallback') is not fallback:raise BoundaryError('FIT_STATUS_SCOPE')
        allowed={'completed'} if not fallback else {'prefix_labels_insufficient','temperature_fit_failed_fallback_Ts' if ref.split(':')[2]=='T' else 'head_fit_failed_fallback_K'}
        if fit.get('status') not in allowed:raise BoundaryError('FIT_STATUS_CATEGORY')
        if not row.get('successful_close') or not row.get('state_event') or not row.get('prediction_event'):raise BoundaryError('INCOMPLETE_OPERATION_BINDING')
        verify_state_file(self.audit.root,row.get('state_artifact',{}))
        path=pathlib.Path(row['prediction_file']['path']);checked(self.audit.root,path)
        if sha_file(path)!=row['prediction_file']['sha256']:raise BoundaryError('PREDICTION_FILE_CHANGED')
        payload=json.loads(path.read_text())
        if payload['ordinals']!=q or payload['valid']!=v or payload['ref']!=ref:raise BoundaryError('PREDICTION_RECORD_JOIN')
        gap=payload['gap']
        if type(payload.get('temperature')) not in (int,float) or not math.isfinite(payload['temperature']) or payload['temperature']<=0:raise BoundaryError('PREDICTION_TEMPERATURE')
        if len(gap)!=len(q) or any((ok and (type(x) not in (int,float) or not math.isfinite(x))) or (not ok and x is not None) for x,ok in zip(gap,v)):raise BoundaryError('PREDICTION_VALUES_VALID_MISMATCH')
        self.rows[ref]=copy.deepcopy(row)
    def finish(self):
        if set(self.rows)!=self.expected or self.audit.poisoned:raise BoundaryError('COHORT_INCOMPLETE')
        for row in self.rows.values():
            verify_state_file(self.audit.root,row['state_artifact'])
            if sha_file(row['prediction_file']['path'])!=row['prediction_file']['sha256']:raise BoundaryError('PREDICTION_CHANGED_BEFORE_SEAL')
        payload={'code_identity':self.code_identity,'audit_head_before_seal':self.audit.head,'rows':[self.rows[k] for k in sorted(self.rows)]}
        token=digest(payload)
        file=self.audit.store_json('seal.json',dict(payload,seal_sha256=token))
        self.audit.event('all_predictions_sealed',seal_sha256=token,file=file)
        self.seal=token;return token
    def release_labels(self,token,loader):
        if self.seal is None or token!=self.seal:raise BoundaryError('SEAL_REQUIRED')
        obj=json.loads((self.audit.root/'seal.json').read_text());got=obj.pop('seal_sha256')
        if got!=token or digest(obj)!=token:raise BoundaryError('SEAL_CHANGED')
        # Recheck persisted prediction bytes immediately before invoking the label loader.
        for row in obj['rows']:
            verify_state_file(self.audit.root,row['state_artifact'])
            if sha_file(row['prediction_file']['path'])!=row['prediction_file']['sha256']:raise BoundaryError('SEALED_PREDICTION_CHANGED')
        event=self.audit.event('Q_labels_release_enter',seal_sha256=token)
        labels=loader()
        if set(labels)!=set(range(1,10)):raise BoundaryError('NINE_LABEL_SETS')
        for p,r in labels.items():
            if r['ordinals']!=self.expected_q[p] or len(r['values'])!=len(self.expected_q[p]) or any(type(y)!=int or y not in (0,1) for y in r['values']):raise BoundaryError('Q_LABEL_JOIN')
        self.audit.event('Q_labels_release_return',parent=event,seal_sha256=token,complete=True)
        return labels
