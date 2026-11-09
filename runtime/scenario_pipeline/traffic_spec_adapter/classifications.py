"""Project captured classes into the current ontology; originals stay in evidence."""
import re


def project_user(user, known):
    positives=user.get('classes')
    unknown=user.get('unobserved_classes',[])
    child_known_negative=('child' in unknown and positives is not None
        and 'pedestrian' not in positives and 'pedestrian' not in unknown)
    if not ((set(positives or [])|set(unknown))-known) and 'source_classifications' not in user and not child_known_negative:
        return user
    result=dict(user)
    result.pop('source_classifications',None)
    if positives is not None:
        result['classes']=[c for c in positives if c in known]
    result['unobserved_classes']=[c for c in unknown if c in known]
    if set(positives or [])-known:
        # An obsolete positive category cannot establish any new legal category.
        result['classes']=result['classes'] or None
        result['unobserved_classes']=sorted(known-set(result['classes'] or []))
    # ATOMS defines a child as a pedestrian who is visibly a child. This uses
    # an observed negative pedestrian classification, not an age default.
    if (result.get('classes') is not None and 'pedestrian' not in result['classes']
            and 'pedestrian' not in result['unobserved_classes']):
        result['unobserved_classes']=[c for c in result['unobserved_classes'] if c!='child']
    return result


def known_classes(library):
    from .adapter import full_core
    text=(full_core(library)/'Vocab/Ontology/RoadUser.lean').read_text()
    block=text.split('namespace RoadUserClass',1)[1].split('end RoadUserClass',1)[0]
    result=set(re.findall(r'\| "([a-z_]+)" =>',block))
    if not result:raise ValueError('No current road-user class codec')
    return result
