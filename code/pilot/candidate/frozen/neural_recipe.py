"""EEGNet1666 and frozen state operations; CPU float32 encoder / float64 heads."""
import copy,random,hashlib
from contracts import NumericalFailure,ValidityStop
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
class NeuralError(ValueError):pass
def setup(seed):
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
 torch.set_num_threads(1)
 if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
 torch.use_deterministic_algorithms(True)
class EEGNet(nn.Module):
 def __init__(self):
  super().__init__()
  self.temporal=nn.Conv2d(1,8,(1,64),bias=False)
  self.bn1=nn.BatchNorm2d(8,eps=1e-5,momentum=.1)
  self.spatial=nn.Conv2d(8,16,(3,1),groups=8,bias=False)
  self.bn2=nn.BatchNorm2d(16,eps=1e-5,momentum=.1)
  self.depth=nn.Conv2d(16,16,(1,16),groups=16,bias=False)
  self.point=nn.Conv2d(16,16,(1,1),bias=False)
  self.bn3=nn.BatchNorm2d(16,eps=1e-5,momentum=.1)
  self.dropout=nn.Dropout(.5);self.head=nn.Linear(256,2)
  for m in self.modules():
   if isinstance(m,(nn.Conv2d,nn.Linear)):
    nn.init.xavier_uniform_(m.weight)
    if m.bias is not None:nn.init.zeros_(m.bias)
   if isinstance(m,nn.BatchNorm2d):
    nn.init.ones_(m.weight);nn.init.zeros_(m.bias);m.running_mean.zero_();m.running_var.fill_(1);m.num_batches_tracked.zero_()
 def features(self,x):
  x=self.bn1(self.temporal(F.pad(x,(31,32,0,0))))
  x=self.dropout(F.avg_pool2d(F.elu(self.bn2(self.spatial(x))),kernel_size=(1,4)))
  x=self.point(self.depth(F.pad(x,(7,8,0,0))))
  x=self.dropout(F.avg_pool2d(F.elu(self.bn3(x)),kernel_size=(1,8)))
  return x.flatten(1)
 def forward(self,x):return self.head(self.features(x))
def state_hash(model):
 h=hashlib.sha256()
 for k,v in sorted(model.state_dict().items()):
  a=v.detach().cpu().numpy();h.update(k.encode());h.update(str(a.dtype).encode());h.update(a.tobytes())
 return h.hexdigest()
def tensor(x):
 a=np.asarray(x,dtype=np.float32)
 if a.ndim!=3 or a.shape[1:]!=(3,512) or len(a)>16 or not np.isfinite(a).all():raise NeuralError("INPUT")
 return torch.from_numpy(a[:,None])
def train_smoke(model,x,y,seed,charge,epochs=5):
 if epochs!=5 or len(x)>32 or len(x)!=len(y):raise NeuralError("SMOKE_WORKLOAD")
 opt=torch.optim.AdamW(model.parameters(),lr=.001,betas=(.9,.999),eps=1e-8,weight_decay=.0001,foreach=False,fused=False)
 rng=np.random.Generator(np.random.PCG64(seed));losses=[]
 model.train()
 for epoch in range(epochs):
  order=rng.permutation(len(x))
  for begin in range(0,len(x),16):
   ids=order[begin:begin+16];charge("steps",1)
   opt.zero_grad(set_to_none=True);z=model(tensor(x[ids]));loss=F.cross_entropy(z,torch.as_tensor(y[ids],dtype=torch.long))
   if not torch.isfinite(loss):raise NeuralError("TRAIN_LOSS_NONFINITE")
   loss.backward();opt.step();losses.append(float(loss.detach()))
 return {"epochs":epochs,"optimizer_steps":len(losses),"losses":losses,"selection":"fixed_fifth_epoch","state_sha256":state_hash(model)}
def features(model,x,charge):
 model.eval();parts=[]
 with torch.no_grad():
  for i in range(0,len(x),16):
   parts.append(charge.forward(model,x[i:i+16],lambda:model.features(tensor(x[i:i+16]))).cpu().numpy().astype(np.float64))
 if not parts:return np.empty((0,256),dtype=np.float64)
 return np.concatenate(parts)
def head_arrays(model):return model.head.weight.detach().cpu().numpy().astype(np.float64),model.head.bias.detach().cpu().numpy().astype(np.float64)
def head_logits(features,W,b):return np.asarray(features,dtype=np.float64)@W.T+b
def _moments(model,layer,x,charge,batch=16):
 if batch>16 or batch<1:raise NeuralError("FORWARD_BATCH")
 sums=squares=None;count=0
 def hook(module,args):
  nonlocal sums,squares,count
  a=args[0].detach().cpu().numpy().astype(np.float64)
  z=a.sum(axis=(0,2,3));zz=np.square(a).sum(axis=(0,2,3));n=a.shape[0]*a.shape[2]*a.shape[3]
  sums=z if sums is None else sums+z;squares=zz if squares is None else squares+zz;count+=n
 handle=layer.register_forward_pre_hook(hook)
 try:
  with torch.no_grad():
   for i in range(0,len(x),batch):
    charge.forward(model,x[i:i+batch],lambda:model(tensor(x[i:i+batch])))
 finally:handle.remove()
 if count==0:raise NeuralError("NO_MOMENTS")
 mean=sums/count;var=squares/count-mean*mean
 tolerance=1e-12*np.maximum(1,squares/count)
 if not np.isfinite(mean).all() or not np.isfinite(var).all() or np.any(var < -tolerance):raise NeuralError("NONFINITE_OR_NEGATIVE_MOMENT")
 return mean,np.maximum(var,0)
def canonical(source,x,charge,batch=16):
 out=copy.deepcopy(source).eval();mom=[]
 for layer in (out.bn1,out.bn2,out.bn3):
  mu,var=_moments(out,layer,x,charge,batch)
  with torch.no_grad():layer.running_mean.copy_(torch.from_numpy(mu));layer.running_var.copy_(torch.from_numpy(var))
  mom.append((mu.copy(),var.copy()))
 return out,tuple(mom)
def update_n(source,source_moments,prefix,charge,k=160,batch=16):
 if len(prefix)<4:return copy.deepcopy(source).eval(),{"status":"prefix_features_insufficient","active":False,"fallback":True,"features":len(prefix)}
 if k not in (0,40,160):raise ValidityStop("N_K_GRID")
 out=copy.deepcopy(source).eval();alpha=len(prefix)/(len(prefix)+k)
 try:
  for layer,(mus,vs) in zip((out.bn1,out.bn2,out.bn3),source_moments):
   try:mut,vt=_moments(out,layer,prefix,charge,batch)
   except NeuralError as exc:
    if str(exc) not in ("NONFINITE_OR_NEGATIVE_MOMENT","NO_MOMENTS"):raise ValidityStop(str(exc)) from exc
    raise NumericalFailure(str(exc)) from exc
   mu=(1-alpha)*mus+alpha*mut;var=(1-alpha)*vs+alpha*vt+alpha*(1-alpha)*(mus-mut)**2
   if not np.isfinite(mu).all() or not np.isfinite(var).all():raise NumericalFailure("N_NONFINITE")
   try:
    with torch.no_grad():
     layer.running_mean.copy_(torch.from_numpy(mu));layer.running_var.copy_(torch.from_numpy(np.maximum(var,0)))
   except RuntimeError as exc:
    if "out of memory" in str(exc).lower():raise
    raise NumericalFailure("BN_BUFFER_CAST_FAILURE") from exc
   except (TypeError,OverflowError) as exc:raise NumericalFailure("BN_BUFFER_CAST_FAILURE") from exc
   if not torch.isfinite(layer.running_mean).all() or not torch.isfinite(layer.running_var).all():raise NumericalFailure("BN_CAST_NONFINITE")
  return out,{"status":"completed","active":True,"fallback":False,"alpha":alpha,"features":len(prefix),"passes":3}
 except (NumericalFailure,FloatingPointError,OverflowError) as exc:
  return copy.deepcopy(source).eval(),{"status":"normalization_failed_fallback_K","active":False,"fallback":True,"reason":str(exc),"atomic_source_restoration":True}
