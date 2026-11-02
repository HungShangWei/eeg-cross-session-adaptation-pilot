"""Fixed empty-feature shape contract; no fitting, forward or file access."""
from contracts import ValidityStop
def ea_transform(ea,epochs,W=None):
 import numpy as np
 a=np.asarray(epochs,dtype=np.float64)
 if a.shape==(0,):a=np.empty((0,3,512),dtype=np.float64)
 if a.ndim!=3 or a.shape[1:]!=(3,512):raise ValidityStop('EA_EPOCH_SHAPE')
 if not len(a):return np.empty((0,6),dtype=np.float64)
 return ea.transform(a,W)
