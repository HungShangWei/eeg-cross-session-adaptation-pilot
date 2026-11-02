"""Isolated trusted data service of the formal run. PREP imports and boundary tests use synthetic doubles only.
Fixed completed-buffer transformations are copied dependencies; not causal streaming.
The full source/target MAT materialization remains disclosed; API isolation is not OS isolation.
"""
import pathlib,hashlib,copy,json,struct,zlib
from audit_core import BoundaryError,digest,verify_state_file
from content_identity import content_identity,Store
class DataService:
    def __init__(self,manifest,audit):
        self.files={(r['participant'],r['container']):r for r in manifest['files']}
        if len(self.files)!=18:raise BoundaryError('EXACT_18_CONTAINERS')
        self.audit=audit;self.store=Store(audit);self.qualified={};self.cache={};self.developed=set();self.scal_released=set();self.frozen={}
    def view_identity(self,view):
        return {'requested':list(view.requested),'ordinals':list(view.neural.ordinals),'valid':list(view.epoch_mask.values),
                'feature_identity':content_identity(view.neural.values),'label_ordinals':list(view.labels.ordinals),
                'label_value_identity':content_identity(view.labels.values)}
    def _bounded_mat(self,path):
        # Same MAT-v5 expansion cap as the exact old trusted service, before scipy allocation.
        expanded=0
        with path.open('rb') as f:
            h=f.read(128)
            if len(h)!=128 or h[126:128] not in (b'IM',b'MI'):raise BoundaryError('MAT_HEADER')
            endian='<' if h[126:128]==b'IM' else '>'
            while tag:=f.read(8):
                self.audit.guard()
                if len(tag)!=8:raise BoundaryError('MAT_TAG')
                kind,size=struct.unpack(endian+'II',tag)
                if kind not in (14,15) or size>134217728:raise BoundaryError('MAT_TAG_BOUND')
                if kind==14:
                    expanded+=size
                    if expanded>536870912:raise BoundaryError('MAT_EXPANSION_BOUND')
                    if len(f.read(size))!=size:raise BoundaryError('MAT_TRUNCATED')
                    f.read((-size)%8)
                else:
                    dec=zlib.decompressobj();remaining=size
                    while remaining:
                        b=f.read(min(65536,remaining))
                        if not b:raise BoundaryError('MAT_TRUNCATED')
                        remaining-=len(b)
                        while b:
                            self.audit.guard();out=dec.decompress(b,65536);expanded+=len(out);b=dec.unconsumed_tail
                            if expanded>536870912:raise BoundaryError('MAT_EXPANSION_BOUND')
                    if not dec.eof or dec.unused_data:raise BoundaryError('MAT_ZLIB')
    def _load(self,person,container):
        import numpy as np
        from scipy.io import loadmat
        from trusted_ingress import structural_mapping
        row=self.files[person,container];p=pathlib.Path(row['path'])
        if p.is_symlink() or p.resolve()!=p or p.suffix!='.mat':raise BoundaryError('MAT_PATH')
        self.audit.guard();h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(65536),b''):self.audit.guard();h.update(b)
        if p.stat().st_size!=row['expected_bytes'] or h.hexdigest()!=row['expected_sha256']:raise BoundaryError('MAT_IDENTITY')
        self.audit.event('trusted_container_materialization_enter',participant=person,container=container,
            source_sha256=h.hexdigest(),complete_container=True,includes_full_labels=True)
        self._bounded_mat(p)
        data=np.atleast_1d(loadmat(p,struct_as_record=False,squeeze_me=True,variable_names=['data'],verify_compressed_data_integrity=True)['data']).reshape(-1)
        groups=[];runs={}
        for index,run in enumerate(data):
            self.audit.guard()
            if not all(hasattr(run,k) for k in ('X','trial','y','fs','classes')):raise BoundaryError('MAT_FIELDS')
            x=run.X;y=np.asarray(run.y).reshape(-1);t=np.asarray(run.trial).reshape(-1)
            if x.ndim!=2 or x.shape[1]!=6 or x.dtype.kind not in 'fi' or float(run.fs)!=250:raise BoundaryError('MAT_CHANNEL_FS')
            if t.dtype.kind not in 'iuf' or y.dtype.kind not in 'iuf' or not np.isfinite(t).all() or not np.isfinite(y).all() or not np.equal(t,np.floor(t)).all() or len(y)!=len(t) or not np.isin(y,[1,2]).all():raise BoundaryError('MAT_LABEL_ONSET_SCHEMA')
            starts=t.astype(np.int64)-1
            if len(starts) and (starts[0]<0 or starts[-1]>=len(x) or np.any(np.diff(starts)<=0)):raise BoundaryError('MAT_CHRONOLOGY')
            classes=[str(v).strip().replace('_',' ') for v in np.asarray(run.classes).reshape(-1)]
            if classes!=['left hand','right hand']:raise BoundaryError('MAT_CLASSES')
            groups.append({'group_index':index,'trial_count':len(t),'trial_start_samples':starts.tolist(),'samples':len(x)})
            runs[index]=(run,starts,y)
        mapping=structural_mapping(groups,container)
        if mapping['selected_group_index']!=row['loader_group_index'] or mapping['physical_session']!=row['physical_session']:raise BoundaryError('PHYSICAL_SESSION')
        self.audit.event('trusted_container_materialization_return',participant=person,container=container,
            source_sha256=row['expected_sha256'],physical_session=mapping['physical_session'],group=mapping['selected_group_index'])
        return runs[mapping['selected_group_index']],groups
    def qualify(self,person):
        from science_contract import split,interval_disjoint
        from trusted_ingress import extract_partition,generic_schema
        from contracts import source_gates
        if person in self.qualified:raise BoundaryError('QUALIFICATION_ONCE')
        source,sg=self._load(person,'T');target,tg=self._load(person,'E')
        ns=len(source[1]);nt=len(target[1]);sp=split(ns,nt);raw={}
        if ns!=self.files[person,'T']['structural_opportunities'] or nt!=self.files[person,'E']['structural_opportunities']:raise BoundaryError('FROZEN_PHYSICAL_TRIAL_COUNTS')
        intervals=[]
        for container,groups in (('T',sg),('E',tg)):
            for row in generic_schema(groups,container,ns,nt,self.files[person,container],person):
                intervals.append((container,row['partition'],*row['analysis_interval']))
                if row['precue_interval']:intervals.append((container,row['partition'],*row['precue_interval']))
                self.audit.event('structural_trial',**row)
        interval_disjoint(intervals)
        for name in ('S-fit','D0','D1','D2'):
            ids=sp.part(name);raw[name]=extract_partition(*source,ids,name,ids[:10] if name=='D1' else ids)
        fit=raw['S-fit'];source_gates(ns,nt,fit['raw'].ordinals,list(fit['labels'].values),fit['precue'].ordinals,raw['D2']['raw'].ordinals)
        self.cache[person]={'source':source,'target':target,'split':sp,'raw_development':raw,'pipe':None,'transformed':{},
            'qualification_content':content_identity({'S_fit_labels':fit['labels'].values,'S_fit_ordinals':fit['raw'].ordinals,'precue_ordinals':fit['precue'].ordinals,'D2_ordinals':raw['D2']['raw'].ordinals})}
        self.qualified[person]=self.audit.event('source_qualification_complete',participant=person,
            source_identity=self.source_input_identity(person),S_fit_ordinals=list(fit['raw'].ordinals),precue_ordinals=list(fit['precue'].ordinals),
            D2_ordinals=list(raw['D2']['raw'].ordinals),source_label_identity=content_identity(fit['labels'].values),preprocessing_started=False)
    def n_source(self,p):return len(self.cache[p]['source'][1])
    def source_input_identity(self,p):
        return {'participant':p,'physical_session':3,'source_sha256':self.files[p,'T']['expected_sha256'],
                'partition':'source-only-development','source_split':self.cache[p]['split'].source if p in self.cache else None}
    def target_container_hashes(self):return {p:self.files[p,'E']['expected_sha256'] for p in range(1,10)}
    def expected_q(self):return {p:list(e['split'].part('Q')) for p,e in self.cache.items()}
    def development(self,p):
        from trusted_ingress import preprocess_development
        if set(self.qualified)!=set(range(1,10)) or p in self.developed:raise BoundaryError('ALL_NINE_QUALIFICATION_REQUIRED')
        e=self.cache[p]
        with self.audit.boundary('qualified_source_development',participant=p,source_identity=self.source_input_identity(p),
                                  qualification_event=self.qualified[p],qualification_content=e['qualification_content']) as out:
            pipe,blocks,failures=preprocess_development(e['raw_development'],self.n_source(p),len(e['target'][1]),self.audit,p)
            # Fixed transformation may legitimately invalidate a qualified raw epoch.
            # Preserve the original post-transform source_gates in preprocess_development;
            # verify the surviving trial/label join rather than require identical row counts.
            raw_fit=e['raw_development']['S-fit'];fit=blocks['S-fit']
            label_lookup=dict(zip(raw_fit['labels'].ordinals,raw_fit['labels'].values))
            if (not set(fit.neural.ordinals).issubset(raw_fit['raw'].ordinals)
                or fit.labels.ordinals!=fit.neural.ordinals
                or tuple(fit.labels.values)!=tuple(label_lookup[i] for i in fit.labels.ordinals)
                or not set(blocks['D2'].neural.ordinals).issubset(e['raw_development']['D2']['raw'].ordinals)):
                raise BoundaryError('QUALIFICATION_CHANGED_AFTER_PREPROCESS')
            out['post_transform_validity']='original source gates retained; no refill or relabelling'
            out['returned_feature_content']={k:self.view_identity(v) for k,v in blocks.items()}
            out['preprocessing_content']=content_identity({'B':pipe.B,'mean':pipe.mean,'std':pipe.std,'floor':pipe.floor})
        e['pipe']=pipe;self.developed.add(p)
        self.store.record('source_preprocessing',{'participant':p,'source_input_identity':self.source_input_identity(p),
            'all_nine_qualification_events':self.qualified,'fit_ordinals':blocks['S-fit'].neural.ordinals,
            'B':pipe.B,'mean':pipe.mean,'std':pipe.std,'floor':pipe.floor,'nuisance':pipe.nuisance,'failures':failures})
        return blocks
    def normalization_identity(self,p):
        pipe=self.cache[p]['pipe']
        return digest(content_identity({'B':pipe.B,'mean':pipe.mean,'std':pipe.std,'floor':pipe.floor}))
    def _block(self,p,which,ids,allowed):
        import numpy as np
        from trusted_ingress import extract_partition
        from contracts import Block,Indexed
        from signal_recipe import SignalError
        if p not in self.developed:raise BoundaryError('PREPROCESSING_NOT_FROZEN')
        e=self.cache[p];pipe=e['pipe'];raw=extract_partition(*e[which],ids,'released',allowed);vals=[];valid=[]
        for ordinal,x in zip(raw['raw'].ordinals,raw['raw'].values):
            self.audit.guard();key=(which,ordinal)
            try:
                if key not in e['transformed']:e['transformed'][key]=pipe.transform(x)
            except SignalError as exc:
                if str(exc)!='COMMON_STRUCTURAL_INVALIDITY':raise
                continue
            vals.append(e['transformed'][key]);valid.append(ordinal)
        a=np.stack(vals) if vals else np.empty((0,3,512),dtype=np.float64)
        lookup=dict(zip(raw['labels'].ordinals,raw['labels'].values));li=tuple(i for i in valid if i in lookup)
        return Block(tuple(ids),Indexed(tuple(valid),pipe.neural(a)),Indexed(tuple(valid),a),
            Indexed(tuple(ids),tuple(i in valid for i in ids)),Indexed(li,tuple(lookup[i] for i in li)))
    def scal(self,p):
        if p in self.scal_released or p not in self.frozen:raise BoundaryError('SCAL_AFTER_FREEZE_ONCE')
        self.scal_released.add(p);ids=self.cache[p]['split'].part('S-cal');return self._block(p,'source',ids,ids)
    def freeze_source(self,p,token,payload):
        if p not in self.developed or p in self.frozen or payload['input_identity']!=self.source_input_identity(p) or digest(payload)!=token:raise BoundaryError('SOURCE_FREEZE_BINDING')
        if set(payload['choices'])!={'T','H','checkpoint'} or set(payload['state_hashes'])!={'1103','2207','3301'}:raise BoundaryError('SOURCE_FREEZE_SCOPE')
        self.audit.event('trusted_source_freeze_received',participant=p,freeze_sha256=token,preprocessing_identity=self.normalization_identity(p))
        self.frozen[p]=token
    def prefix(self,request):
        p=request['person']
        if p not in self.scal_released or request['container_sha256']!=self.files[p,'E']['expected_sha256'] or request['requested_ordinals']!=list(range(10)) or request['budget']!=10:raise BoundaryError('PREFIX_REQUEST')
        with self.audit.boundary('trusted_prefix_view',participant=p,recipient=request['recipient'],
            call_id=request['call_id'],container_sha256=request['container_sha256'],allowed_label_ordinals=list(range(10))) as outcome:
            view=self._block(p,'target',range(10),range(10));view.validate(tuple(range(10)))
            outcome['actual_label_ordinals']=list(view.labels.ordinals)
        reply=dict(request,valid=list(view.epoch_mask.values),label_ordinals=list(view.labels.ordinals),
            sample_onset_indices=[int(x) for x in self.cache[p]['target'][1][:10]])
        return reply,view
    def q_features(self,p):return self._block(p,'target',self.cache[p]['split'].part('Q'),())
    def scoring_labels(self,token):
        path=self.audit.root/'seal.json'
        if not path.exists():raise BoundaryError('SERVICE_SEAL_REQUIRED')
        obj=json.loads(path.read_text());stored=obj.pop('seal_sha256')
        expected={f'{p}:{s}:{m}:10' for p in range(1,10) for s in (1103,2207,3301) for m in ('T','H')}
        if stored!=token or digest(obj)!=token or len(obj['rows'])!=54 or {r['ref'] for r in obj['rows']}!=expected:raise BoundaryError('SERVICE_SEAL_IDENTITY')
        for row in obj['rows']:
            verify_state_file(self.audit.root,row['state_artifact'])
            if not row['successful_close'] or hashlib.sha256(pathlib.Path(row['prediction_file']['path']).read_bytes()).hexdigest()!=row['prediction_file']['sha256']:raise BoundaryError('SERVICE_OUTPUT_CHANGED')
        return {p:{'ordinals':list(e['split'].part('Q')),'values':[int(e['target'][2][i])-1 for i in e['split'].part('Q')]} for p,e in self.cache.items()}
