"""Independent float64 primary arithmetic; no RNG and no file/data/model entry.
Uses fixed df=8 t critical value; percentile interpolation is implemented separately.
Synthetic tests compare this to the frozen original recipe before any science grant.
"""
import math
from audit_core import BoundaryError
T975_DF8=2.306004135204166
def bounds(values):
    x=[float(v) for v in values]
    if len(x)!=9 or not all(math.isfinite(v) for v in x):raise BoundaryError('NINE_FINITE')
    mean=math.fsum(x)/9;sd=math.sqrt(math.fsum((v-mean)**2 for v in x)/8);d=T975_DF8*sd/3
    return {'mean':mean,'lower':mean-d,'upper':mean+d,'two_sided95':[mean-d,mean+d],'degenerate_sd':sd==0,'n':9,'df':8,'alpha':.025}
def percentile(values,indices):
    if tuple(indices.shape)!=(10000,9):raise BoundaryError('EXISTING_INDEX_SCHEMA')
    x=[float(v) for v in values]
    if len(x)!=9 or not all(math.isfinite(v) for v in x):raise BoundaryError('BOOTSTRAP_VALUES')
    means=[]
    for row in indices:
        ids=[int(i) for i in row]
        if any(i<0 or i>=9 for i in ids):raise BoundaryError('INDEX_DOMAIN')
        means.append(math.fsum(x[i] for i in ids)/9)
    means.sort()
    def quantile(q):
        pos=9999*q;lo=math.floor(pos);hi=math.ceil(pos)
        return means[lo]+(pos-lo)*(means[hi]-means[lo])
    lo,hi=quantile(.025),quantile(.975)
    return {'lower':lo,'upper':hi,'two_sided95':[lo,hi]}
def useful(J,C):
    jb,cb=bounds(J),bounds(C);n=sum(j<=.2 and c>=.5 for j,c in zip(J,C));why=[]
    if jb['upper']>=.2:why.append('J_bound_failed')
    if cb['lower']<=.5:why.append('C_bound_failed')
    if n<7:why.append('7_of_9_failed')
    against=jb['lower']>.2 or cb['upper']<.5
    return {'established':not why,'J':jb,'C':cb,'participant_guard':n,'reasons':why,
            'interpretation':'evidence_against_utility_bound' if against else 'utility_not_established_with_current_precision' if why else 'useful_established'}
def active(fits):
    if len(fits)!=9 or any(len(r)!=3 or any(type(v)!=bool for v in r) for r in fits):raise BoundaryError('ACTIVE_FIT_SCHEMA')
    n=sum(sum(row)>=2 for row in fits);return n>=6,n
def robust(base,passes):return 'no_bootstrap_upgrade' if not base else 'robust' if all(passes) else 'MODEL_DEPENDENT'
def independent_primary(people,Tfits,Hfits,indices):
    if [r['participant'] for r in people]!=list(range(1,10)):raise BoundaryError('PERSON_ORDER')
    JT,JH,CT,CH=([r[k] for r in people] for k in ('T_J','H_J','T_C','H_C'));delta=[a-b for a,b in zip(JT,JH)];db=bounds(delta)
    ni='ESTABLISHED' if db['upper']<.02 else 'CONTRADICTED' if db['lower']>.02 else 'INCONCLUSIVE'
    ut,uh=useful(JT,CT),useful(JH,CH);at,nt=active(Tfits);ah,nh=active(Hfits)
    base='HP1_NI_CONTRADICTED' if ni=='CONTRADICTED' else 'HP1_NI_INCONCLUSIVE' if ni=='INCONCLUSIVE' else 'HP1_SUPPORTED' if ut['established'] and at else 'NI_T_FIT_INADEQUATE' if ut['established'] else 'NI_T_USEFUL_NOT_ESTABLISHED' if at else 'NI_T_USEFUL_NOT_ESTABLISHED_AND_FIT_INADEQUATE'
    label=base+f"__T{int(ut['established'])}_H{int(uh['established'])}_A{int(at)}"
    boot={k:percentile(v,indices) for k,v in (('delta',delta),('T_J',JT),('T_C',CT),('H_J',JH),('H_C',CH))}
    return {'status':'EVALUATED','t_model_base_label':label,'delta':db,'NI':ni,'T_usefulness':ut,'H_usefulness':uh,
            'T_active_people':nt,'H_active_people':nh,'H_useful_fitted_reference':bool(uh['established'] and ah),
            'H_reference_robustness':robust(uh['established'],[boot['H_J']['upper']<.20,boot['H_C']['lower']>.50]),
            'bootstrap':boot,'robustness_status':robust(base=='HP1_SUPPORTED',[boot['delta']['upper']<.02,boot['T_J']['upper']<.20,boot['T_C']['lower']>.50]),
            'contradiction_model_dependent':bool(ni=='CONTRADICTED' and not boot['delta']['lower']>.02)}
def compare_primary(original,independent,absolute_tolerance=1e-10):
    if absolute_tolerance!=1e-10:raise BoundaryError('FROZEN_TOLERANCE')
    def walk(a,b,path):
        if isinstance(a,dict):
            if not isinstance(b,dict) or set(a)!=set(b):raise BoundaryError('PRIMARY_KEYS:'+path)
            for k in a:walk(a[k],b[k],path+'/'+k)
        elif isinstance(a,(list,tuple)):
            if len(a)!=len(b):raise BoundaryError('PRIMARY_LENGTH:'+path)
            for i,(v,w) in enumerate(zip(a,b)):walk(v,w,path+'/'+str(i))
        elif type(a) is float:
            if not math.isfinite(a) or not math.isfinite(b) or abs(a-b)>absolute_tolerance:raise BoundaryError('PRIMARY_NUMERIC:'+path)
        elif a!=b:raise BoundaryError('PRIMARY_DISCRETE:'+path)
    walk(original,independent,'');return True
