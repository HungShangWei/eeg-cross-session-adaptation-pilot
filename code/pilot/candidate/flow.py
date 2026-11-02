"""Actual prefix/adapt/state/forward/close/seal call wiring; injectable synthetic adapters.
The real adapter is imported only by the separately gated launch entry.
"""
import copy
from audit_core import Feedback,Cohort,BoundaryError,state_change,digest
from content_identity import content_identity
def execute_core(service,adapter,audit,code_identity):
    # Qualification must complete for all nine before any source preprocessing fit.
    for person in range(1,10):service.qualify(person)
    if set(service.qualified)!=set(range(1,10)):raise BoundaryError('ALL_NINE_BEFORE_FIT')
    feedback=Feedback(audit,service.target_container_hashes())
    cohort=Cohort(audit,service.expected_q(),code_identity)
    sources={}
    outcomes={key:{'status':'NOT_STARTED'} for key in cohort.expected}
    try:
        for person in range(1,10):sources[person]=adapter.prepare_source(person,service)
        for person in range(1,10):
            for seed in (1103,2207,3301):
                for method in ('T','H'):
                    ref=f'{person}:{seed}:{method}:10';request=feedback.request(person,seed,method)
                    status='aborted';finish=None
                    try:
                        # Provider returns one exact view; receipt is persisted before adapter sees it.
                        reply,view=service.prefix(request)
                        with audit.boundary('trusted_view_fingerprint',recipient=ref,call_id=request['call_id'],purpose='receipt identity'):
                            view_identity=service.view_identity(view)
                        feedback.receive(request,reply,view_identity)
                        state=adapter.clone_source(sources[person][seed])
                        before=adapter.state_identity(state,person)
                        with audit.boundary('target_adaptation',recipient=ref,call_id=request['call_id'],before=before,
                                            prefix_identity=view_identity,code_identity=code_identity) as fit:
                            state=adapter.adapt(state,method,view,feedback,request)
                            after=adapter.state_identity(state,person)
                            fit['allowed_changes']=state_change(method,before,after)
                            fit['after']=after
                        stored=adapter.store_state(ref,state,before,after,request)
                        # No labels are permitted in the Q feature view.
                        q=service.q_features(person)
                        with audit.boundary('target_prediction',recipient=ref,state_event=stored['event_id'],
                                            state_identity=after,Q_identity=adapter.view_identity(q)) as predicted:
                            payload=adapter.predict(ref,state,q)
                            if adapter.state_identity(state,person)!=after:raise BoundaryError('FORWARD_MUTATED_STATE')
                            file=audit.store_json('predictions/'+ref+'.json',payload)
                            predicted['prediction_file']=file
                        prediction_event=audit.event('prediction_persisted',recipient=ref,state_event=stored['event_id'],prediction_file=file)
                        fit_status=state['status'];allowed={'completed','prefix_labels_insufficient',
                            'temperature_fit_failed_fallback_Ts' if method=='T' else 'head_fit_failed_fallback_K'}
                        if fit_status.get('status') not in allowed:raise BoundaryError('UNRECOGNIZED_FIT_STATUS')
                        fallback=fit_status['status']!='completed'
                        if fit_status.get('fallback') is not fallback or fit_status.get('active') is not (not fallback):raise BoundaryError('FIT_STATUS_FLAGS')
                        status='protocol_fallback' if fallback else 'completed'
                        finish=feedback.end(ref,request['call_id'],status,parent=prediction_event)
                        row={'ref':ref,'ordinals':payload['ordinals'],'valid':payload['valid'],'denominator':len(payload['ordinals']),
                             'outcome':status,'fit_status':state['status'],'state_event':stored['event_id'],'state_artifact':stored,
                             'prediction_event':prediction_event,'successful_close':True,'end_event':finish,
                             'prediction_file':file,'source_identity':adapter.state_identity(sources[person][seed],person)}
                        cohort.add(row);outcomes[ref]={'status':status}
                    except BaseException as exc:
                        outcomes[ref]={'status':'ABORTED','error_type':type(exc).__name__}
                        if finish is None:feedback.end(ref,request['call_id'],'aborted')
                        raise
    except BaseException:
        # Missing/failed operations remain explicit; no cohort seal or labels follow.
        if not audit.poisoned:audit.store_json('operation_outcomes_incomplete.json',outcomes)
        raise
    token=cohort.finish();labels=cohort.release_labels(token,lambda:service.scoring_labels(token))
    return adapter.score_sealed(cohort,labels,token)
