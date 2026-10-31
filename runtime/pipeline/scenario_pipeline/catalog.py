"""Evidence-checked, incremental vocabulary and domain-filtered driving-cell catalog."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
from itertools import islice, product
import json
from pathlib import Path
from pipeline_paths import CATALOG_DIR, require_artifact_path

import os
import tempfile

ROOT = Path(__file__).resolve().parent
DIMS = ('road_layouts', 'maneuvers', 'controls')
CELL_DIMS = ('layout', 'maneuver', 'control')
STATUSES = {'grounded', 'plausible_ungrounded', 'structurally_infeasible'}
DOMAINS = frozenset({
    'general', 'railway', 'school', 'parking_curb', 'roundabout',
    'pedestrian_crossing', 'intersection', 'highway_multilane', 'rural',
    'work_zone', 'emergency', 'cycling', 'transit',
    'road_geometry', 'public_place',
})
PLACEHOLDER_IDS = {'unspecified', 'none', 'null', 'unknown', 'any'}
VEHICLE_ROLE_IDS = {
    'leading_vehicle', 'following_vehicle', 'oncoming_vehicle',
    'overtaking_vehicle', 'overtaken_vehicle', 'previously_stopped_vehicle',
    'vehicle_in_intersection', 'circulating_vehicle', 'through_traffic',
    'downstream_traffic', 'oncoming_left_turner', 'vehicle_from_right',
    'left_turning_vehicle', 'approaching_traffic', 'passing_vehicle',
    'vehicle_entering_parking', 'vehicle_stopped_for_pedestrian',
    'parked_vehicle', 'convoy_vehicle',
}
PARTICIPANT_STATE_IDS = {
    'approaching_emergency_vehicle', 'moving_emergency_vehicle',
    'pedestrian_in_crosswalk',
}
PARTIES = frozenset({
    'motor_vehicle_driver', 'bus_driver', 'taxi_driver', 'emergency_vehicle_driver',
    'heavy_vehicle_driver',
    'cycle_or_scooter_operator', 'motorcycle_or_moped_operator',
    'horse_drawn_vehicle_operator', 'pedestrian', 'small_wheeled_device_user',
    'delivery_device_operator', 'nonmotor_vehicle_operator', 'vehicle_occupant',
    'unspecified',
})
SPECIALIZED_DRIVERS = frozenset({'bus_driver', 'taxi_driver', 'emergency_vehicle_driver',
                                 'heavy_vehicle_driver'})
DRIVER_PARTIES = frozenset({'motor_vehicle_driver'}) | SPECIALIZED_DRIVERS


def cell_values(terms, dimension):
    """Scope placeholders can annotate laws but cannot describe a cell axis."""
    return sorted(key for key, term in terms[dimension].items()
                  if key not in PLACEHOLDER_IDS and not term.get('is_placeholder', False))


def pattern_layouts(pattern, annotation, terms):
    if pattern['road_layouts']:
        return pattern['road_layouts']
    if annotation.get('layout_scope') == 'broad':
        return cell_values(terms, 'road_layouts')
    return []


def law_cooccurrence(analysis):
    """Three terms named in one law, even if no joint fact pattern supports them."""
    result = {}
    for law_id, annotation in analysis.items():
        for triple in product(*(annotation[d] for d in DIMS)):
            result.setdefault(triple, set()).add(law_id)
    return result


def formation_reasons(triple, terms, cooccurrence):
    tags = [set(terms[d][term]['domains']) for d,term in zip(DIMS,triple)]
    common = set.intersection(*tags) - {'general'}
    specific = [group for group in tags if 'general' not in group]
    compatible = len(specific) < 2 or bool(set.intersection(*specific))
    reasons = []
    if common:
        reasons.append('shared_domain')
    if compatible and any('general' in group for group in tags):
        reasons.append('general_domain')
    if triple in cooccurrence:
        reasons.append('law_cooccurrence')
    return reasons, sorted(common)


def party_support(analysis, vocabulary):
    """Collect actor support from citations for each maneuver and control."""
    support = {d:{term:set() for term in vocabulary[d]} for d in ('maneuvers', 'controls')}
    for annotation in analysis.values():
        for dimension in support:
            for term, parties in annotation['term_parties'][dimension].items():
                if term in support[dimension]:
                    support[dimension][term].update(parties)
    known = set(analysis)
    for dimension in support:
        for term, parties in support[dimension].items():
            if set(vocabulary[dimension][term]['source_laws']) - known:
                parties.add('unspecified')
    return support


def compatible_parties(maneuver_parties, control_parties):
    """A general motor-vehicle obligation also covers specialized motor drivers."""
    maneuver, control = set(maneuver_parties), set(control_parties)
    candidates = (maneuver & control) - {'unspecified'}
    if 'motor_vehicle_driver' in maneuver:
        candidates.update(control & SPECIALIZED_DRIVERS)
    if 'motor_vehicle_driver' in control:
        candidates.update(maneuver & SPECIALIZED_DRIVERS)
    if candidates:
        return sorted(candidates), 'compatible'
    if 'unspecified' in maneuver or 'unspecified' in control:
        return [], 'unresolved'
    return [], 'actor_mismatch'


def actor_summary(cells):
    grounded, plausible, party_sets = Counter(), Counter(), Counter()
    statuses = Counter()
    for cell in cells:
        if cell['grounding'] == 'grounded':
            parties = sorted(cell['grounding_by_party'])
            grounded.update(parties)
            party_sets['+'.join(parties)] += 1
        elif cell['grounding'] == 'plausible_ungrounded':
            plausible.update(cell['candidate_ego_parties'])
            statuses[cell['actor_status']] += 1
    return {
        'grounded_by_party': dict(sorted(grounded.items())),
        'grounded_by_party_set': dict(sorted(party_sets.items())),
        'grounded_driver_cells': sum(bool(set(cell.get('grounding_by_party', {})) & DRIVER_PARTIES)
                                     for cell in cells if cell['grounding'] == 'grounded'),
        'plausible_by_candidate_party': dict(sorted(plausible.items())),
        'plausible_actor_status': dict(sorted(statuses.items())),
        'plausible_driver_cells': sum(bool(set(cell.get('candidate_ego_parties', [])) & DRIVER_PARTIES)
                                      for cell in cells if cell['grounding'] == 'plausible_ungrounded'),
    }


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError as exc:
                    raise ValueError(f'{path}:{number}: invalid JSON') from exc


def batches(records, size):
    if size < 1:
        raise ValueError('batch size must be positive')
    records = iter(records)
    while batch := list(islice(records, size)):
        yield batch


def corpus_file(path):
    path = Path(path).resolve()
    if path.is_file():
        return path
    for suffix in ('laws/full_list/laws.jsonl', 'full_list/laws.jsonl', 'laws.jsonl'):
        if (path / suffix).is_file():
            return path / suffix
    raise ValueError(f'No canonical laws.jsonl at supplied corpus path: {path}')


def load_json(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write('{\n')
            for i, (key, item) in enumerate(value.items()):
                if i:
                    handle.write(',\n')
                handle.write(json.dumps(key) + ': ')
                if key == 'cells' and isinstance(item, list):
                    handle.write('[\n')
                    for j, cell in enumerate(item):
                        if j:
                            handle.write(',\n')
                        handle.write(json.dumps(cell, ensure_ascii=False, separators=(',', ':')))
                    handle.write('\n]')
                else:
                    handle.write(json.dumps(item, ensure_ascii=False, indent=2))
            handle.write('\n}\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def term_index(document):
    result = {}
    for dimension in DIMS:
        result[dimension], names = {}, {}
        for term in document[dimension]:
            if term['id'] in result[dimension]:
                raise ValueError(f'Duplicate canonical ID: {term["id"]}')
            domains = term.get('domains')
            if (not isinstance(domains, list) or not domains or
                any(not isinstance(tag, str) or tag not in DOMAINS for tag in domains) or
                len(domains) != len(set(domains))):
                raise ValueError(f'Invalid or missing domains for {dimension}:{term["id"]}')
            result[dimension][term['id']] = term
            for name in [term['id'], term['description'], *term.get('synonyms', [])]:
                normal = ' '.join(name.casefold().replace('_', ' ').split())
                if normal in names and names[normal] != term['id']:
                    raise ValueError(f'Ambiguous synonym {name}: consolidate canonical terms')
                names[normal] = term['id']
    overlap = set(result['road_layouts']) & set(result['controls'])
    if overlap:
        raise ValueError('Layout/control category leakage: ' + ', '.join(sorted(overlap)))
    roles = set(result['controls']) & (VEHICLE_ROLE_IDS | PARTICIPANT_STATE_IDS)
    if roles:
        raise ValueError('Participant roles or states belong in annotation conditions: ' + ', '.join(sorted(roles)))
    return result


def validate_annotation(law, annotation, terms):
    if annotation.get('text_sha256') != digest(law['text']):
        raise ValueError(f'{law["id"]}: law text changed; review annotation again')
    def evidence(items):
        if not items:
            raise ValueError(f'{law["id"]}: missing evidence')
        for item in items:
            if item['law_id'] != law['id'] or not item['quote'] or item['quote'] not in law['text']:
                raise ValueError(f'{law["id"]}: evidence is not an exact quote of this law')
            parties = item.get('obligated_parties')
            if not isinstance(parties, list) or not parties or set(parties) - PARTIES or len(parties) != len(set(parties)):
                raise ValueError(f'{law["id"]}: evidence needs reviewed obligated_parties')
    evidence(annotation.get('evidence'))
    cited_parties = {party for item in annotation['evidence'] for party in item['obligated_parties']}
    term_parties = annotation.get('term_parties')
    if not isinstance(term_parties, dict) or set(term_parties) != set(DIMS):
        raise ValueError(f'{law["id"]}: missing term_parties')
    for dimension in DIMS:
        for term in annotation[dimension]:
            if term not in terms[dimension]:
                raise ValueError(f'{law["id"]}: unknown {dimension} term {term}')
        if set(term_parties[dimension]) != set(annotation[dimension]):
            raise ValueError(f'{law["id"]}: term_parties must cover {dimension}')
        for parties in term_parties[dimension].values():
            if not isinstance(parties, list) or not parties or set(parties) - PARTIES or len(parties) != len(set(parties)):
                raise ValueError(f'{law["id"]}: invalid term obligated parties')
            if not set(parties) <= cited_parties:
                raise ValueError(f'{law["id"]}: term party lacks citation support')
    for pattern in annotation['fact_patterns']:
        evidence(pattern.get('evidence'))
        parties = pattern.get('obligated_parties')
        if not isinstance(parties, list) or not parties or set(parties) - PARTIES or len(parties) != len(set(parties)):
            raise ValueError(f'{law["id"]}: fact pattern needs reviewed obligated_parties')
        if not set(parties) <= {party for item in pattern['evidence'] for party in item['obligated_parties']}:
            raise ValueError(f'{law["id"]}: fact pattern party lacks citation support')
        for dimension in DIMS:
            if (dimension != 'road_layouts' and not pattern[dimension]) or not set(pattern[dimension]) <= set(annotation[dimension]):
                raise ValueError(f'{law["id"]}: invalid fact pattern {dimension}')
            for term in pattern[dimension]:
                if not set(parties) <= set(term_parties[dimension][term]):
                    raise ValueError(f'{law["id"]}: fact pattern party lacks term support')


def build(corpus_path, output_dir, terms_path, annotations_path, batch_size=40,
          constraints_path=None, sync_corpus=False):
    output = Path(output_dir) / 'vocabulary_catalog.json'
    previous = load_json(output, {})
    terms = term_index(load_json(terms_path))
    incoming_annotations = {}
    for annotation in read_jsonl(annotations_path):
        if annotation['law_id'] in incoming_annotations:
            raise ValueError('Duplicate law annotation: ' + annotation['law_id'])
        incoming_annotations[annotation['law_id']] = annotation
    # A complete replacement corpus retires absent laws; batches extend by default.
    # Keep previous cells only as stable identity and metadata references.
    sources = {} if sync_corpus else deepcopy(previous.get('law_records', {}))
    analysis = {} if sync_corpus else deepcopy(previous.get('law_analysis', {}))
    incoming_ids = set()
    for batch in batches(read_jsonl(corpus_file(corpus_path)), batch_size):
        for law in batch:
            for required in ('id', 'text', 'title', 'source'):
                if not isinstance(law.get(required), str) or not law[required]:
                    raise ValueError(f'Law missing nonempty {required}')
            if law['id'] in incoming_ids:
                raise ValueError('Duplicate law ID: ' + law['id'])
            incoming_ids.add(law['id'])
            if law['id'] not in incoming_annotations:
                raise ValueError(f'{law["id"]}: missing annotation; run prepare and review the batch')
            annotation = incoming_annotations[law['id']]
            validate_annotation(law, annotation, terms)
            sources[law['id']], analysis[law['id']] = law, annotation
    if not incoming_ids:
        raise ValueError('Empty corpus')
    legacy_sources = set() if sync_corpus else set(previous.get('legacy_source_laws', []))
    vocabulary = {}
    for dimension in DIMS:
        vocabulary[dimension] = {t['id']: deepcopy(t) for t in previous.get(dimension, [])}
        for item in vocabulary[dimension].values():
            if sync_corpus:
                item['source_laws'], item['evidence'] = [], []
            else:
                legacy_sources.update(set(item['source_laws']) - sources.keys())
                item['source_laws'] = sorted(set(item['source_laws']) - incoming_ids)
                item['evidence'] = [e for e in item.get('evidence', []) if e['law_id'] not in incoming_ids]
        for law_id, annotation in analysis.items():
            for term_id in annotation[dimension]:
                if term_id not in vocabulary[dimension]:
                    if term_id not in terms[dimension]:
                        raise ValueError(f'Missing retained term definition: {term_id}')
                    vocabulary[dimension][term_id] = deepcopy(terms[dimension][term_id])
                    vocabulary[dimension][term_id].update(source_laws=[], evidence=[])
                item = vocabulary[dimension][term_id]
                item['source_laws'] = sorted(set(item['source_laws']) | {law_id})
                item.setdefault('evidence', [])
                for evidence in annotation['evidence']:
                    term_evidence = dict(evidence, obligated_parties=
                                         annotation['term_parties'][dimension][term_id])
                    if term_evidence not in item['evidence']:
                        item['evidence'].append(term_evidence)
                if term_id in terms[dimension]:
                    item['description'] = terms[dimension][term_id]['description']
                    item['domains'] = terms[dimension][term_id]['domains']
                    item['synonyms'] = sorted(set(item.get('synonyms', [])) |
                                              set(terms[dimension][term_id].get('synonyms', [])))
        vocabulary[dimension] = {k:v for k,v in vocabulary[dimension].items() if v['source_laws']}
    grounded = {}
    for law_id, annotation in analysis.items():
        for pattern in annotation['fact_patterns']:
            for triple in product(pattern_layouts(pattern, annotation, vocabulary),
                                  pattern['maneuvers'], pattern['controls']):
                for party in pattern['obligated_parties']:
                    grounded.setdefault(triple, {}).setdefault(party, set()).add(law_id)
    cooccurrence = law_cooccurrence(analysis)
    support = party_support(analysis, vocabulary)
    old_cells, all_ids = {}, set()
    for cell in previous.get('cells', []):
        triple = tuple(cell[d] for d in CELL_DIMS)
        if triple in old_cells or cell['cell_id'] in all_ids:
            raise ValueError('Previous catalog has duplicate cells or cell IDs')
        old_cells[triple] = cell
        all_ids.add(cell['cell_id'])
        if cell.get('grounding', cell.get('status')) == 'grounded':
            for party, laws in cell.get('grounding_by_party',
                                        {'unspecified':cell.get('source_laws', [])}).items():
                retained = set() if sync_corpus else set(laws) - incoming_ids
                if retained:
                    grounded.setdefault(triple, {}).setdefault(party, set()).update(retained)
    rules = load_json(constraints_path, []) if constraints_path else previous.get('physical_constraints', [])
    infeasible = {}
    for rule in rules:
        if rule.get('basis') != 'mechanical_physical' or not rule.get('justification', '').strip():
            raise ValueError('Infeasibility needs a mechanical_physical basis and justification')
        triple = tuple(rule[d] for d in CELL_DIMS)
        if any(t not in vocabulary[d] for d,t in zip(DIMS,triple)):
            raise ValueError('Constraint references an unknown term')
        if triple in infeasible:
            raise ValueError('Duplicate physical constraint')
        infeasible[triple] = rule
    cells = []
    general_impact = {(d, term_id):Counter()
                      for d in DIMS for term_id in cell_values(vocabulary, d)
                      if 'general' in vocabulary[d][term_id]['domains']}
    law_exceptions = []
    next_id = max((int(c[1:]) for c in all_ids if c.startswith('C') and c[1:].isdigit()), default=0) + 1
    next_id = max(next_id, previous.get('next_cell_id', 1))
    theoretical_product = 1
    for dimension in DIMS:
        theoretical_product *= len(cell_values(vocabulary, dimension))
    for triple in product(*(cell_values(vocabulary, d) for d in DIMS)):
        old = old_cells.get(triple, {})
        grounding_by_party = {party:sorted(laws) for party, laws in
                              sorted(grounded.get(triple, {}).items()) if laws}
        cited = sorted({law for laws in grounding_by_party.values() for law in laws})
        status = 'grounded' if cited else 'plausible_ungrounded'
        if triple in infeasible:
            if cited:
                raise ValueError(f'Physical constraint contradicts grounded fact pattern: {triple}')
            status = 'structurally_infeasible'
        elif old.get('grounding', old.get('status')) == 'structurally_infeasible' and not constraints_path:
            if not old.get('justification'):
                raise ValueError('Legacy infeasible cell has no justification')
            if not cited:
                status = 'structurally_infeasible'
        reasons, shared = formation_reasons(triple, vocabulary, cooccurrence)
        if status == 'plausible_ungrounded':
            for dimension, term_id in zip(DIMS, triple):
                impact = general_impact.get((dimension, term_id))
                if impact is not None:
                    if 'general_domain' in reasons:
                        impact['retained_via_general'] += 1
                    elif not reasons:
                        impact['filtered_despite_general'] += 1
            if reasons == ['law_cooccurrence']:
                law_exceptions.append(dict(**dict(zip(CELL_DIMS, triple)),
                                           source_laws=sorted(cooccurrence[triple])))
        if status == 'plausible_ungrounded' and not reasons:
            continue
        cid = old.get('cell_id')
        if not cid:
            while f'C{next_id:03d}' in all_ids:
                next_id += 1
            cid = f'C{next_id:03d}'
            next_id += 1
        cell = dict(old, cell_id=cid, **dict(zip(CELL_DIMS, triple)), grounding=status,
                    source_laws=cited)
        cell.pop('status', None)
        cell.pop('justification', None)
        cell.pop('formation_basis', None)
        cell.pop('shared_domains', None)
        cell.pop('cooccurrence_laws', None)
        cell.pop('grounding_by_party', None)
        cell.pop('candidate_ego_parties', None)
        cell.pop('actor_status', None)
        if status == 'plausible_ungrounded':
            cell['formation_basis'] = reasons
            cell['candidate_ego_parties'], cell['actor_status'] = compatible_parties(
                support['maneuvers'][triple[1]], support['controls'][triple[2]])
            if shared:
                cell['shared_domains'] = shared
            if 'law_cooccurrence' in reasons:
                cell['cooccurrence_laws'] = sorted(cooccurrence[triple])
        if status == 'structurally_infeasible':
            cell['justification'] = infeasible.get(triple, old)['justification']
        if status == 'grounded':
            cell['grounding_by_party'] = grounding_by_party
        cells.append(cell)
    result = dict(previous, schema_version=2,
        semantics={
            'layout_values':'Road topology, geometry, lane structure or district context; values may overlap and describe partial geometry.',
            'control_values':'Specific activation object or participant, including fixed markings, signs, curb colors and designated spaces. Vehicle position and state belong in law-level conditions.',
            'unspecified_layout':'Scope marker in an annotation only; never a cell layout. A broad law can ground cells on real layouts through a wildcard.',
            'maneuver_values':'Intent or task; compelled braking/yielding are responses, not new goals.',
            'grounding':'Reviewed joint fact pattern, including prohibited behavior. Not a permission or full activation predicate.',
            'actor_attribution':'Grounded cells cite obligated parties by law; plausible cells list candidate ego parties supported by maneuver and control citations. Layout-source actors do not constrain ego.',
            'plausible_ungrounded':'Candidate not ruled out by supplied physical constraints; not proof of map realizability.',
            'plausible_cell_filter':'Only plausible_ungrounded cells are filtered: compatible specific domains with general as an item-level wildcard, or all three terms named in one law.',
            'evidence':'Exact text in law_analysis and law_records; full conditions and exceptions remain operative.'},
        **{d:sorted(vocabulary[d].values(), key=lambda t:t['id']) for d in DIMS},
        law_records=sources, law_analysis=analysis, legacy_source_laws=sorted(legacy_sources - sources.keys()),
        physical_constraints=rules, next_cell_id=next_id, cells=cells)
    annotation_provenance = {law_id:{'law_id':law_id,'annotation_version':digest(json.dumps(a,sort_keys=True)),
        'review_status':a.get('review_status','unknown'),'reviewed_at':a.get('reviewed_at')} for law_id,a in analysis.items()}
    result['provenance'] = {'review_status':'unreviewed','annotations':annotation_provenance}
    for dimension in DIMS:
        for term in result[dimension]:
            term['provenance']={'annotation_refs':sorted(law for law in term['source_laws'] if law in annotation_provenance)}
    term_sources={dimension:{term['id']:term['source_laws'] for term in result[dimension]} for dimension in DIMS}
    for cell in cells:
        refs=set(cell.get('source_laws',[])) | set(cell.get('cooccurrence_laws',[]))
        for dimension,field in zip(DIMS,CELL_DIMS):
            refs.update(term_sources[dimension][cell[field]])
        cell['provenance']={'annotation_refs':sorted(law for law in refs if law in annotation_provenance)}
    result['summary'] = {'laws_processed':len(analysis), 'incoming_laws':len(incoming_ids),
                         **{d:len(cell_values(vocabulary,d)) for d in DIMS}, 'cells':len(cells),
                         'structural_cross_product':theoretical_product,
                         'filtered_plausible_cells':theoretical_product-len(cells),
                         'grounding_counts':dict(Counter(c['grounding'] for c in cells)),
                         'actor_counts':actor_summary(cells)}
    validate_catalog(result)
    atomic_json(output, result)
    atomic_json(Path(output_dir) / 'summary.json', result['summary'])
    atomic_json(Path(output_dir) / 'domain_filter_audit.json', {
        'general_terms': [dict(axis=dimension, id=term_id,
                               retained_via_general=impact['retained_via_general'],
                               filtered_despite_general=impact['filtered_despite_general'])
                          for (dimension, term_id), impact in sorted(general_impact.items())],
        'law_cooccurrence_exception_count': len(law_exceptions),
        'law_cooccurrence_exception_examples': law_exceptions[:50],
    })
    return result['summary']


def validate_catalog(catalog):
    terms = term_index(catalog)
    source_ids = set(catalog.get('law_records', {})) | set(catalog.get('legacy_source_laws', []))
    for dimension in DIMS:
        for term in terms[dimension].values():
            if not term.get('source_laws'):
                raise ValueError('Ungrounded vocabulary term: ' + term['id'])
            if source_ids and not set(term['source_laws']) <= source_ids:
                raise ValueError('Unknown term source laws')
            for evidence in term.get('evidence', []):
                law = catalog.get('law_records', {}).get(evidence['law_id'])
                if law and evidence['quote'] not in law['text']:
                    raise ValueError('Invalid term evidence quote')
                annotation = catalog.get('law_analysis', {}).get(evidence['law_id'])
                if annotation and set(evidence.get('obligated_parties', [])) != set(
                    annotation['term_parties'][dimension][term['id']]):
                    raise ValueError('Term evidence has incorrect obligated parties')
    theoretical = 1
    for dimension in DIMS:
        theoretical *= len(cell_values(terms, dimension))
    joint = {}
    for law_id, annotation in catalog.get('law_analysis', {}).items():
        law = catalog['law_records'][law_id]
        validate_annotation(law, annotation, terms)
        for pattern in annotation['fact_patterns']:
            for triple in product(pattern_layouts(pattern, annotation, terms),
                                  pattern['maneuvers'], pattern['controls']):
                for party in pattern['obligated_parties']:
                    joint.setdefault(triple, {}).setdefault(party, set()).add(law_id)
    cooccurrence = law_cooccurrence(catalog.get('law_analysis', {}))
    support = party_support(catalog.get('law_analysis', {}), terms)
    valid_axes = {d:set(cell_values(terms,d)) for d in DIMS}
    triples, ids = set(), set()
    for cell in catalog['cells']:
        triple = tuple(cell[d] for d in CELL_DIMS)
        if triple in triples or cell['cell_id'] in ids:
            raise ValueError('Duplicate cell')
        triples.add(triple); ids.add(cell['cell_id'])
        if any(t not in terms[d] for d,t in zip(DIMS,triple)):
            raise ValueError('Unknown cell term')
        if any(t not in valid_axes[d] for d,t in zip(DIMS,triple)):
            raise ValueError('Placeholder crossed into a cell')
        if cell['grounding'] not in STATUSES:
            raise ValueError('Invalid grounding status')
        reasons, shared = formation_reasons(triple, terms, cooccurrence)
        if cell['grounding'] == 'grounded':
            if not cell['source_laws']:
                raise ValueError('Grounded cell without source laws')
            by_party = cell.get('grounding_by_party')
            if (not isinstance(by_party, dict) or not by_party or set(by_party) - PARTIES or
                any(not isinstance(laws, list) or not laws for laws in by_party.values()) or
                set(cell['source_laws']) != {law for laws in by_party.values() for law in laws}):
                raise ValueError('Grounded cell has invalid obligated-party citations')
            for party, laws in by_party.items():
                for law_id in laws:
                    if law_id in catalog.get('law_analysis', {}) and law_id not in joint.get(triple, {}).get(party, set()):
                        raise ValueError('Grounded cell party lacks a joint fact pattern')
            for law_id in cell['source_laws']:
                if source_ids and law_id not in source_ids:
                    raise ValueError('Unknown grounded-cell source')
                if law_id in catalog.get('law_analysis', {}) and not any(
                    law_id in laws for laws in joint.get(triple, {}).values()):
                    raise ValueError('Grounded cell lacks a joint fact pattern')
        elif cell['grounding'] == 'plausible_ungrounded':
            if triple in joint:
                raise ValueError('Directly supported cell mislabeled plausible')
            if not reasons or cell.get('formation_basis') != reasons:
                raise ValueError('Plausible cell lacks a valid domain or law-cooccurrence basis')
            if cell.get('shared_domains', []) != shared:
                raise ValueError('Plausible cell has incorrect shared domains')
            if cell.get('cooccurrence_laws', []) != sorted(cooccurrence.get(triple, set())):
                raise ValueError('Plausible cell has incorrect law co-occurrence evidence')
            expected_parties, expected_status = compatible_parties(
                support['maneuvers'][triple[1]], support['controls'][triple[2]])
            if cell.get('candidate_ego_parties') != expected_parties or cell.get('actor_status') != expected_status:
                raise ValueError('Plausible cell has incorrect ego actor classification')
        if cell['grounding'] == 'structurally_infeasible' and not cell.get('justification'):
            raise ValueError('Infeasible cell without justification')
    constrained = {tuple(rule[d] for d in CELL_DIMS)
                   for rule in catalog.get('physical_constraints', [])}
    for triple in product(*(cell_values(terms,d) for d in DIMS)):
        if triple in triples:
            continue
        if triple in joint or triple in constrained or formation_reasons(triple, terms, cooccurrence)[0]:
            raise ValueError('Eligible cell missing from catalog')
    if catalog.get('summary', {}).get('actor_counts') != actor_summary(catalog['cells']):
        raise ValueError('Incorrect actor summary counts')
    return {'valid':True, 'cells':len(triples), 'structural_cross_product':theoretical}


def prepare(corpus_path, destination, annotations_path, size):
    known = {a['law_id']:a for a in read_jsonl(annotations_path)} if Path(annotations_path).exists() else {}
    pending = (dict(law=law, text_sha256=digest(law['text']), review_status='pending')
               for law in read_jsonl(corpus_file(corpus_path))
               if law['id'] not in known or known[law['id']]['text_sha256'] != digest(law['text']))
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for i, batch in enumerate(batches(pending, size), 1):
        path = target / f'batch-{i:04d}.json'
        if path.exists():
            raise ValueError(f'Refusing to overwrite review work: {path}; choose a fresh batch directory')
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        count += len(batch)
    return {'pending_laws':count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('build', 'prepare'):
        p = sub.add_parser(command)
        p.add_argument('--corpus', required=True, type=Path)
        p.add_argument('--output-dir', type=Path, default=CATALOG_DIR)
        p.add_argument('--annotations', type=Path, default=ROOT/'data/law_annotations.jsonl')
        p.add_argument('--batch-size', type=int, default=40)
        if command == 'build':
            p.add_argument('--terms', type=Path, default=ROOT/'data/terms.json')
            p.add_argument('--physical-constraints', type=Path)
            p.add_argument('--sync-corpus', action='store_true',
                           help='Treat input as the complete corpus: retire absent laws and unsupported terms, preserving surviving cell IDs')
    p = sub.add_parser('validate')
    p.add_argument('catalog', type=Path)
    args = parser.parse_args()
    if hasattr(args, "output_dir"):
        args.output_dir = require_artifact_path(args.output_dir)
    try:
        if args.command == 'build':
            result = build(args.corpus, args.output_dir, args.terms, args.annotations,
                           args.batch_size, args.physical_constraints, args.sync_corpus)
        elif args.command == 'prepare':
            result = prepare(args.corpus, args.output_dir, args.annotations, args.batch_size)
        else:
            result = validate_catalog(load_json(args.catalog))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    main()
