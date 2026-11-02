"""Frozen primary J/C scoring only. Computes decision loss J and coverage C per instance from
supplied prediction records and evaluation labels, then averages them over three seeds and nine
participants. No data loading or model operation is performed here.
Synthetic fixtures are engineering tests; execution status is documented in docs/VALIDATION_SCOPE.md.
"""
import math
from audit_core import BoundaryError,ordinals
def score(saved,labels,expected_q):
    q=ordinals(expected_q)
    if saved['ordinals']!=q or labels['ordinals']!=q:raise BoundaryError('SCORER_ORDINAL_JOIN')
    y=labels['values'];gap=saved['gap'];valid=saved['valid'];T=saved['temperature']
    if not q or not(len(q)==len(y)==len(gap)==len(valid)):raise BoundaryError('SCORER_DENOMINATOR')
    if type(T) not in (int,float) or not math.isfinite(T) or T<=0:raise BoundaryError('TEMPERATURE')
    if any(type(v)!=bool for v in valid) or any(type(v)!=int or v not in (0,1) for v in y):raise BoundaryError('LABEL_OR_MASK_SCHEMA')
    accepted=wrong=invalid=0
    for g,truth,ok in zip(gap,y,valid):
        if not ok:
            if g is not None:raise BoundaryError('INVALID_GAP_MUST_BE_NULL')
            invalid+=1;continue
        if type(g) not in (int,float) or not math.isfinite(g):raise BoundaryError('VALID_GAP')
        if abs(g)/T>=math.log(3.):
            accepted+=1;wrong+=int((g>0)!=truth)
    n=len(q);deferred=n-accepted
    return {'J':(wrong+.25*deferred)/n,'C':accepted/n,'denominator':n,
            'accepted':accepted,'accepted_wrong':wrong,'deferred':deferred,'technical_deferred':invalid}
def aggregate(rows):
    expected={(p,s,m) for p in range(1,10) for s in (1103,2207,3301) for m in ('T','H')}
    keyed={}
    for r in rows:
        key=(r['participant'],r['seed'],r['method'])
        if key not in expected or key in keyed:raise BoundaryError('AGGREGATE_DUPLICATE_OR_SCOPE')
        if not all(type(r[k]) in (int,float) and math.isfinite(r[k]) for k in ('J','C')):raise BoundaryError('AGGREGATE_NONFINITE')
        if not (0<=r['J']<=1 and 0<=r['C']<=1):raise BoundaryError('METRIC_RANGE')
        keyed[key]=r
    if set(keyed)!=expected:raise BoundaryError('INCOMPLETE_54_INSTANCES')
    people=[]
    for p in range(1,10):
        out={'participant':p}
        for m in ('T','H'):
            for metric in ('J','C'):out[m+'_'+metric]=math.fsum(keyed[p,s,m][metric] for s in (1103,2207,3301))/3
        out['T_minus_H_J']=out['T_J']-out['H_J'];people.append(out)
    return {'participants':people,'n':9,'group':{key:math.fsum(r[key] for r in people)/9 for key in ('T_J','H_J','T_C','H_C','T_minus_H_J')}}
def original_primary_inference(people,Tfits,Hfits,existing_indices):
    # Frozen function applies exactly the existing t/usefulness/robustness recipe.
    from inference_contract import hp1
    return hp1([r['T_J'] for r in people],[r['H_J'] for r in people],
        [r['T_C'] for r in people],[r['H_C'] for r in people],Tfits,Hfits,existing_indices)
