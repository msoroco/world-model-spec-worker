"""Source-backed repair of actor-review uncertainty without changing cell facts."""
POLICY = """Actor review identifies ego subjects compatible with the fixed maneuver.
Use the catalog's explicit partial-geometry semantics: a layout is not assumed to
exhaust the entire scene, and objects are not assumed to occupy the same road
segment without evidence. Compatible unstated relationships are context needs.
Separate unresolved actor identity/eligibility from scene realization concerns.
Record geometry, control-governance and map-support concerns in scene_requirements
with their exact fixed facts; they remain feasibility prerequisites and must not
be discarded. Scene concerns alone do not invalidate an otherwise identified
actor or require inventing a new cell. Genuine actor ambiguity stays unresolved.
scene_requirements is a list of {prior_issue,description,fixed_facts:[{axis,id,quote}]};
quote exact supplied term descriptions for every named fixed fact. This list
preserves scene prerequisites for downstream feasibility, never confirms them.
"""

CONTRACT = POLICY + '''Independently resolve each prior actor-review uncertainty using the
full supplied law texts, verified structures and exact fixed vocabulary facts.
An assignment is an ego subject performing the fixed cell maneuver. A duty about
another participant does not force an incompatible ego assignment. In particular,
if a subject cannot perform the fixed maneuver, record a justified exclusion,
not an unresolved demand to change the cell. Do not invent a pedestrian backing a
vehicle or silently change layout, maneuver, control, declared actors or IDs.
Grounding/source-law citations do not require actors. Preserve all original
catalog-declared roles; independently review provisional additions. Compatible
unstated vehicle/person subtypes remain conditional candidates. Real ambiguity or
missing facts remain unresolved; do not remove blockers merely to advance.
Return {reviews:[{cell_id,assignments:[{actor,reason}],unresolved:[string],
excluded_subjects:[{prior_issue,subject,law_id,law_quote,
fixed_fact:{axis:layout|maneuver|control,id,quote},reason}],
scene_requirements:[{prior_issue,description,fixed_facts:[{axis,id,quote}]}],
resolution_notes:[{prior_issue,disposition:assigned|excluded|unresolved|scene_context,actor,reason}]}]}.
Account for every prior unresolved string exactly once in resolution_notes.
Excluded dispositions need matching excluded_subjects with an exact quotation
from the cited CURRENT law and an exact quotation from the fixed term description.
Assigned dispositions name an actor actually assigned in the result. An unresolved
disposition retains an explicit unresolved entry. A scene_context disposition preserves the issue in scene_requirements with exact
fixed-fact quotations and a named missing relationship or capability. It is a
feasibility prerequisite, not a claim that a compatible scene exists. Do not
propose new cells, schemas, judgments, legal values or outcomes.'''


def validate_resolution(planner,payload,result):
    from .law_planning import sha
    planner.validate('actors',payload,result)
    for review in result['reviews']:
        cell=review['cell_id']
        prior=payload['prior_reviews'][cell]
        if sha(prior)!=payload['prior_review_hashes'][cell]:raise ValueError('Actor-resolution prior-review hash mismatch')
        notes=review.get('resolution_notes',[])
        assigned={v['actor'] for v in review['assignments']}
        removed={v['reason']:v['actor'] for v in prior['assignments'] if v['actor'] not in assigned}
        required=set(prior['unresolved'])|set(removed)
        allowed=set(prior['unresolved'])|{v['reason'] for v in prior['assignments']}
        noted={v['prior_issue'] for v in notes}
        if len(notes)!=len(noted) or not required<=noted or not noted<=allowed:
            raise ValueError('Incomplete prior actor-uncertainty accounting')
        excluded=review.get('excluded_subjects',[])
        for proof in excluded:
            if proof['prior_issue'] not in allowed:raise ValueError('Unknown actor-exclusion issue')
            law=planner.laws.get(proof['law_id'])
            if not law or not proof.get('law_quote') or proof['law_quote'] not in law['text'] or not proof.get('reason') or not proof.get('subject'):
                raise ValueError('Unverified actor-exclusion law evidence')
            fact=proof['fixed_fact'];axis=fact['axis']
            terms={'layout':'road_layouts','maneuver':'maneuvers','control':'controls'}
            if axis not in terms or fact['id']!=planner.cells[cell][axis]:
                raise ValueError('Actor exclusion changed fixed cell facts')
            term=next((v for v in planner.catalog[terms[axis]] if v['id']==fact['id']),{})
            if not fact.get('quote') or fact['quote'] not in term.get('description',''):
                raise ValueError('Unverified actor-exclusion fixed-fact quotation')
        for note in notes:
            if not note.get('reason'):raise ValueError('Missing actor-resolution rationale')
            disposition=note['disposition']
            if disposition=='assigned':
                if note['prior_issue'] in removed:raise ValueError('Removed provisional actor needs exclusion or unresolved evidence')
                if note.get('actor') not in {v['actor'] for v in review['assignments']}:
                    raise ValueError('Resolved actor is not assigned')
            elif disposition=='excluded':
                if not any(v['prior_issue']==note['prior_issue'] for v in excluded):
                    raise ValueError('Actor exclusion lacks source-backed proof')
            elif disposition=='scene_context':
                requirements=[v for v in review.get('scene_requirements',[]) if v['prior_issue']==note['prior_issue']]
                if not requirements:raise ValueError('Scene uncertainty silently dropped')
                for requirement in requirements:
                    if not requirement.get('description') or not requirement.get('fixed_facts'):raise ValueError('Missing scene prerequisite evidence')
                    for fact in requirement['fixed_facts']:
                        fields={'layout':'road_layouts','maneuver':'maneuvers','control':'controls'}
                        if fact.get('axis') not in fields or fact['id']!=planner.cells[cell][fact['axis']]:raise ValueError('Scene prerequisite changed fixed facts')
                        term=next((v for v in planner.catalog[fields[fact['axis']]] if v['id']==fact['id']),{})
                        if not fact.get('quote') or fact['quote'] not in term.get('description',''):raise ValueError('Unverified scene prerequisite quotation')
            elif disposition=='unresolved':
                if not review['unresolved']:raise ValueError('Unresolved actor blocker silently dropped')
            else:raise ValueError('Invalid actor-resolution disposition')
    return len(result['reviews'])


def validate_scene_requirements(planner,cell,review):
    requirements=review.get('scene_requirements',[])
    if not isinstance(requirements,list):raise ValueError('Scene prerequisites must be a list')
    for requirement in requirements:
        if not requirement.get('prior_issue') or not requirement.get('description') or not requirement.get('fixed_facts'):
            raise ValueError('Missing scene prerequisite evidence')
        for fact in requirement['fixed_facts']:
            fields={'layout':'road_layouts','maneuver':'maneuvers','control':'controls'}
            if fact.get('axis') not in fields or fact['id']!=planner.cells[cell][fact['axis']]:
                raise ValueError('Scene prerequisite changed fixed facts')
            term=next((v for v in planner.catalog.get(fields[fact['axis']],[]) if v['id']==fact['id']),{})
            if not fact.get('quote') or fact['quote'] not in term.get('description',''):
                raise ValueError('Unverified scene prerequisite quotation')
