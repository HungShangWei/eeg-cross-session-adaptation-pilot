"""Resource guard of the formal run: original C01 quantities, new-run ledger only.
Formal execution remains separately authorized; synthetic tests never relax this policy.
"""
import os,time,json,re,pathlib
from native_helper import native_call,PS
from audit_core import BoundaryError
GIB=1073741824
class ResourceGuard:
    def __init__(self,audit,config):
        self.audit=audit;self.config=config;self.start=time.monotonic();self.last=0.;self.work_end=time.monotonic_ns()+3540_000_000_000;self.cleanup_end=self.work_end+60_000_000_000
        self.in_sample=False;self.baseline_without_run=None
    def event(self,**row):
        # Native helper records without recursively invoking the resource callback.
        old=self.audit.guard;self.audit.guard=lambda:None
        try:self.audit.event('resource_native',detail=row)
        finally:self.audit.guard=old
        return True
    def check(self,initial=False):
        if self.in_sample:return
        if time.monotonic()-self.start>=3540:raise BoundaryError('FORMAL_TIME_LIMIT')
        if not initial and time.monotonic()-self.last<.25:return
        self.in_sample=True
        try:
            vm,_=native_call(self,['/usr/bin/vm_stat']);pressure,_=native_call(self,['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level']);text,_=native_call(self,PS)
            match=re.search(r'page size of (\d+) bytes',vm)
            if not match or 'Swapouts:' not in vm:raise BoundaryError('VM_SCHEMA')
            size=int(match[1]);counts=[]
            for name in ('free','inactive','speculative'):
                v=re.findall(r'^Pages '+name+r':\s+(\d+)\.\s*$',vm,re.M)
                if len(v)!=1:raise BoundaryError('VM_FIELD')
                counts.append(int(v[0]))
            available=sum(counts)*size;rows={}
            for line in text.splitlines():
                f=line.split()
                if len(f)!=10:raise BoundaryError('PS_SCHEMA')
                rows[int(f[0])]={'ppid':int(f[1]),'rss':int(f[8])*1024}
            ids={os.getpid()}
            while True:
                new=ids|{pid for pid,row in rows.items() if row['ppid'] in ids}
                if new==ids:break
                ids=new
            rss=sum(rows[pid]['rss'] for pid in ids if pid in rows)
            ds=os.statvfs(self.audit.root);disk=ds.f_bavail*ds.f_frsize
            if int(pressure.strip())!=1 or available<(16*GIB if initial else 8*GIB+512*1048576):raise BoundaryError('FORMAL_RAM_OR_PRESSURE')
            if rss+512*1048576>4*GIB or rss+512*1048576>9464643584:raise BoundaryError('FORMAL_MEMORY_CAP')
            if disk<15*GIB+8*1048576:raise BoundaryError('SSD_FLOOR')
            allocated=0;seen=set()
            # All configured preparation, run and retained resource roots are included in the same 2 GiB cap.
            for root in map(pathlib.Path,(self.config['parent_prep_root'],self.config['prep_root'],self.config['run_root'],*self.config['retained_accounted_roots'])):
                for base,dirs,files in os.walk(root,followlinks=False):
                    for name in dirs+files:
                        if (pathlib.Path(base)/name).is_symlink():raise BoundaryError('NEW_ROOT_SYMLINK')
                    for name in files:
                        st=(pathlib.Path(base)/name).stat();key=(st.st_dev,st.st_ino)
                        if key not in seen:seen.add(key);allocated+=st.st_blocks*512
            if allocated+8*1048576>2*GIB:raise BoundaryError('PREP_PLUS_RUN_DISK_CAP')
            if self.baseline_without_run is None:
                total=0;original_inodes=set()
                for root in map(pathlib.Path,self.config['controlled_roots']):
                    if not root.exists():continue
                    for base,dirs,files in os.walk(root,followlinks=False):
                        dirs[:]=[d for d in dirs if not (pathlib.Path(base)/d).is_symlink()]
                        for name in files:
                            path=pathlib.Path(base)/name
                            if path.is_symlink():continue
                            st=path.stat();key=(st.st_dev,st.st_ino)
                            if key not in original_inodes:original_inodes.add(key);total+=st.st_blocks*512
                self.baseline_without_run=total
            # Conservative bound: prep directories already in baseline are counted
            # again here for the global cap, never to enlarge allowed storage.
            if allocated+self.baseline_without_run+8*1048576>12*GIB:raise BoundaryError('CONTROLLED_TOTAL_DISK_CAP')
            self.last=time.monotonic()
            self.event(A_est_bytes=available,pressure=int(pressure.strip()),process_tree_rss=rss,disk_available_bytes=disk,prep_plus_run_allocated_bytes=allocated)
        finally:self.in_sample=False
