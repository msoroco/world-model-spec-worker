"""Original-law semantic stages for the posted-speed comparison."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'proposals'
AID = HERE.name
ASSIGNMENT = json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
LAW, CELL, ACTOR = (ASSIGNMENT[k] for k in ('law_id', 'cell_id', 'actor'))
QUOTE = ASSIGNMENT['law']['text']
TEMPLATE = LAW+'@'+ACTOR


def write(name, obj):
    path = OUT/(name+'.json')
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    refs = {}
    relevance = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
            'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'Frozen paved-road travel cell. Public authority and governed portion require original source.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write('relevance-batch', relevance)
    refs['relevance'] = write('relevance', relevance)
    judgments = [
        ('posted by a public authority', 'Authored sign pixels and map signal do not establish original public-authority posting.', 'dev.speed_limit_sign', 'public_authority_posting'),
        ('particular portion of highway being traversed', 'Source-bound sign position, direction, governed extent and ego route must be joined.', 'drv.within_signed_zone', 'governed_highway_portion'),
        ('rate of speed greater than that posted', 'Measure original Native velocity over the governed interval; requested speed is only controller input.', 'kin.speed', 'native_map')]
    refs['judgment_observables'] = []
    for i, (phrase, note, name, source) in enumerate(judgments, 1):
        refs['judgment_observables'].append(write('judgment_observables_'+str(i), {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original 600-frame Native motion and synchronized four-camera source.'}],
                'context_inputs': [{'name': source, 'unit': 'structured',
                    'description': 'Independently reviewed original posting, extent and sign-passage source.'}],
                'sweep_dimensions': [{'name': 'requested_speed_mph', 'unit': 'mph',
                    'description': 'Controlled below, at and above posting speed requests; not a legal verdict.'}],
                'landmarks': [], 'recording_needs': [{'name': 'measured_speed_vs_posted_limit', 'unit': 'mph',
                    'description': 'Full governed-zone actor velocity time series and source-hashed posting.'}],
                'limitations': ['Original posting and highway extent remain review gated.',
                    'Requested speed cannot substitute for measured speed or legal judgment.']}}))
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'quote': QUOTE,
        'status': 'draft', 'structure': {'activation': {
            'description': 'Person drives on the particular highway portion with a public-authority posted speed.',
            'source_clause': 'drive or operate a vehicle of any kind or character'},
            'obligation': {'description': 'Drive at no rate greater than the public-authority posting for that portion.',
                'type': 'must_not', 'source_clause': 'A rate of speed greater than that posted by a public authority for the particular portion of highway being traversed'},
            'exceptions': [], 'timing': {'description': 'Measure throughout the sourced governed portion after sign passage.'},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _, _ in judgments]},
        'parameter_refs': [{'name': 'requested_speed_mph', 'kind': 'controller',
            'range_or_domain': [25, 30, 35]}]}
    refs['template'] = write('template', template)
    refs['bindings'] = write('bindings', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'posted_speed_travel_request',
            'source': 'frozen C179819 cell and authored sign/route request; original authority unverified'}],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [], 'variable_parameters': [{'name': 'requested_speed_mph',
            'kind': 'controller', 'range_or_domain': [25, 30, 35], 'used_by_laws': [LAW]}]})
    cases = json.loads((OUT/'cases.json').read_text())
    cases['sweep_specs'][0]['judgment_refs'] = template['structure']['judgment_calls_needed']
    refs['cases'] = write('cases', cases)
    index = OUT/'semantic-index.json'
    index.write_text(json.dumps({'assignment_id': AID, 'format': 'worker-semantic-delivery',
        'stages': refs}, indent=2, ensure_ascii=False)+'\n')
    return {'selected_cases': 3, 'judgment_observables': len(judgments),
        'index_sha256': hashlib.sha256(index.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
