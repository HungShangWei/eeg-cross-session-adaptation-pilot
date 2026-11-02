"""Explicit synthetic-only persistence fixture; no scientific modules."""
import sys,pathlib
C=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(C))
from audit_core import Audit,Feedback
root=pathlib.Path(sys.argv[1]).resolve()
if C.parent/'tmp' not in root.parents:raise SystemExit('FIXTURE_WRITE_SCOPE')
a=Audit(root,'SYNTHETIC_CHILD','FIXTURE');f=Feedback(a,{p:str(p)*64 for p in range(1,10)})
r=f.request(1,1103,'T');reply=dict(r,valid=[True]*10,label_ordinals=list(range(10)),sample_onset_indices=list(range(100,110)))
identity={'requested':list(range(10)),'ordinals':list(range(10)),'label_ordinals':list(range(10)),'valid':[True]*10,'synthetic':True}
f.receive(r,reply,identity);f.use(r['recipient'],r['call_id'],'class_gate',{'synthetic':True});f.end(r['recipient'],r['call_id'],'protocol_fallback');a.close()
