"""Lossless sharing of semantic analysis across cells with common fixed axes."""
from collections import defaultdict

CONTRACT = '''Evaluate ALL laws for ALL declared actors of EVERY supplied cell.
Cells share layout/maneuver so common reasoning may be reused; controls and actor
assignments can differ and MUST be checked independently. Return only
{decision_groups:[{cell_ids:[exact IDs],law_id,actor,decision,quote,relevance_type,
confidence,reason,required_context}]}. A group means each listed cell/actor/law
has exactly this decision and evidence, independently checked. Split groups when
controls, subjects, context or reasons differ. Every Cartesian product member
(law x actor for that specific cell) must occur exactly once. One exact actor ID
per group; never merge actors or substitute a driver for a pedestrian/cyclist.
Decision is relevant|conditional|irrelevant|unresolved. Positive quotations must
be exact substrings of the CURRENT target law. relevance_type is
specific_match|general_duty; confidence high|medium|low; required_context is a list.
Compatible unstated facts imply conditional relevance, with named missing context.
Irrelevant requires a concrete contradiction of fixed facts or subject scope;
uncertain exclusions are unresolved. Deliberately consider general duties.
Do not use grounding, source_laws, domain tags, keywords, or absent citations as
hard filters. Do not assert judgment values, activation, legal verdicts or labels.
Grouping is output compression only: no listed cell may inherit an unchecked
actor, an exclusion or a contextual assumption from its neighbours.'''


TENSOR_CONTRACT = CONTRACT.replace('law_id,actor,decision','law_id,actors:[exact actor IDs],decision').replace(
    'One exact actor ID\nper group; never merge actors or substitute a driver for a pedestrian/cyclist.',
    'Use distinct, explicitly enumerated actor IDs, checked independently; never substitute a driver for a pedestrian/cyclist.') + """
Each group covers the exact Cartesian product cell_ids x actors for its law.
Every actor must actually be assigned to EVERY listed cell. Partition groups when
actor scope, confidence, context, reason or outcome differs. Enumerated arrays
share identical evidence only; individual actor decisions remain independent.
Never use both/all/driver-like aliases in place of exact IDs. Keep reasons concise.
"""


def cell_groups(cells, reviews, size=25):
    if type(size) is not int or size<1:
        raise ValueError('Cell batch size must be a positive integer')
    common = defaultdict(list)
    for cell_id,review in reviews.items():
        if review['unresolved'] or not review['assignments']:
            continue
        cell = cells[cell_id]
        common[cell['layout'],cell['maneuver']].append(cell_id)
    result=[]
    for axis,ids in sorted(common.items()):
        ids.sort()
        for offset in range(0,len(ids),size):
            selected=ids[offset:offset+size]
            result.append({'cells':selected,'actors_by_cell':{
                c:sorted(a['actor'] for a in reviews[c]['assignments']) for c in selected}})
    return result


def expand_groups(payload,result,allow_actor_lists=False):
    """Require exact actor-specific coverage before expanding a shared result."""
    expected={(c,a,k) for c in payload['cells'] for a in payload['actors_by_cell'][c] for k in payload['laws']}
    if not isinstance(result.get('decision_groups'),list):
        raise ValueError('Missing compressed decision groups')
    seen=set();expanded=[]
    for group in result['decision_groups']:
        ids=group.get('cell_ids')
        if not isinstance(ids,list) or not ids or any(not isinstance(c,str) for c in ids) or len(set(ids))!=len(ids):
            raise ValueError('Group requires distinct explicit cell IDs')
        parties=group.get('actors') if allow_actor_lists and 'actors' in group else [group.get('actor')]
        if 'actors' in group and (not allow_actor_lists or 'actor' in group):
            raise ValueError('Ambiguous actor group')
        if not isinstance(parties,list) or not parties or any(not isinstance(a,str) for a in parties) or len(set(parties))!=len(parties):
            raise ValueError('Group requires distinct explicit actor IDs')
        for cell in ids:
            for actor in parties:
                key=(cell,actor,group.get('law_id'))
                if key not in expected or key in seen:
                    raise ValueError('Duplicate or unknown grouped cell/actor/law decision')
                seen.add(key)
                expanded.append(dict({k:v for k,v in group.items() if k not in ('cell_ids','actors','actor')},cell_id=cell,actor=actor))
    if seen!=expected:
        raise ValueError('Incomplete grouped cell/actor/law accounting')
    return expanded
