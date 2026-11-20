"""Project captured classes into the current ontology; originals stay in evidence."""
import re


def classify(blueprint, attributes, known, physical_classification=None):
    """Class answers from bound native type/attributes, never model-name substrings."""
    attributes = attributes or {}
    positives = set(); decided = set()
    basic = {'motor_vehicle','motorcycle','moped','bicycle','pedestrian','child','bus','truck'}
    if blueprint.startswith('walker.'):
        positives.add('pedestrian');decided.update(known-{'child','pedestrian_with_white_cane_or_guide_animal'})
        if attributes.get('age') == 'child':positives.add('child');decided.add('child')
        elif attributes.get('age') == 'adult':decided.add('child')
    elif blueprint.startswith('vehicle.'):
        decided.update({'pedestrian','child'})
        base = attributes.get('base_type')
        if base in ('car','bus','truck','motorcycle','bicycle'):
            decided.update(basic-({'moped'} if base == 'motorcycle' else set()))
            positives.add('motor_vehicle' if base in ('car','bus','truck') else base)
            # ATOMS: a trailer lacks motive power; this source role is powered.
            if base in ('car','bus','truck'):decided.add('trailer')
            if base in ('bus','truck'):positives.add(base)
    elif physical_classification and physical_classification.get('physical_class') == 'animal':
        if 'animal' not in known:
            raise ValueError('Source animal classification is unsupported by installed Core')
        positives.add('animal');decided.update(basic)
    else:return None,sorted(known)
    if positives-known:raise ValueError('Source class is unsupported by installed Core')
    return sorted(positives),sorted(known-decided-positives)


def apply_classification(user, positives, unknown):
    """Preserve compatible positive facts; never default unresolved roles false."""
    if positives is None:return user
    result = dict(user)
    result['classes'] = sorted(set(positives)|(set(user.get('classes') or [])&set(unknown)))
    result['unobserved_classes'] = sorted(set(unknown)-set(result['classes']))
    result.pop('source_classifications',None)
    return result


def project_user(user, known, observation=None):
    if observation is not None:
        positives, unknown = classify(observation['blueprint'], observation.get('blueprint_attributes'),
                                      known, observation.get('physical_classification'))
        if positives is not None:
            return project_user(apply_classification(user,positives,unknown),known)
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


def structure_refinements(library):
    """Read the exact current Core codec/ancestors and executable refines rule."""
    from .adapter import full_core
    core=full_core(library)
    vocab=(core/'Vocab/Ontology/Structure.lean').read_text()
    atoms=(core/'Vocab/Atoms.lean').read_text()
    expected='def StructureKind.refines (a b : StructureKind) : Bool := a == b || a.ancestors.contains b'
    if expected not in atoms:raise ValueError('Unsupported pinned Core StructureKind.refines declaration')
    codec=dict((native,label) for label,native in re.findall(r'\| "([a-z_]+)" => some \.([A-Za-z]+)',vocab))
    block=vocab.split('def ancestors : StructureKind → List StructureKind',1)[1].split('def isAbstract',1)[0]
    result={label:{label} for label in codec.values()}
    for native,values in re.findall(r'\| \.([A-Za-z]+) => \[(.*?)\]',block):
        if native not in codec:raise ValueError('Unknown Core structure ancestor codec')
        result[codec[native]].update(codec[x] for x in re.findall(r'\.([A-Za-z]+)',values))
    return result


def normalize_structure_kinds(scene, verified, refinements):
    """Clear only masks contradicted by exact source-verified positive facts.

    A source kind fact does not certify inventory completeness, geometry, a
    subtype, or any unrelated classification. Never trust the trace label alone.
    """
    changed=0;added=0;verified_count=0;unverified=[];added_masks=[]
    for region in scene.get('structures',[]):
        facts=set(verified.get(region['id'],()))
        if not facts:
            if region.get('unobserved_kinds'):unverified.append(region['id'])
            continue
        label=region['kind']
        if any(fact not in refinements.get(label,set()) for fact in facts):
            raise ValueError('Source verified kind differs from exported structure identity')
        contradicted=set().union(*(refinements[f] for f in facts))
        old=region.get('unobserved_kinds',[]);new=[m for m in old if m not in contradicted]
        changed+=len(old)-len(new);verified_count+=1
        # Removing an ancestor mask must not reveal an unproved subtype label
        # or an intermediate ancestor. Preserve those distinct unknown answers.
        unresolved=refinements[label]-contradicted
        extra=sorted(unresolved-set(new))
        if extra:
            new.extend(extra);added+=len(extra)
            added_masks.append({'region':region['id'],'kinds':extra,'reason':'ancestor_only_kind_proof'})
        if new!=old:
            if new:region['unobserved_kinds']=new
            else:region.pop('unobserved_kinds',None)
    return {'verified_positive_regions':verified_count,'contradictory_masks_removed':changed,
            'unverified_subtype_masks_added':added,'added_subtype_masks':added_masks,
            'unverified_masked_region_ids':unverified}
