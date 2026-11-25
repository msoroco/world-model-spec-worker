"""Source-inventoried synthetic fixtures for public qualifier compatibility."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
PACKAGE = HERE / 'qualifier-saved-package'
BASE = json.loads((HERE / 'diagnostic-controlled_2.json').read_text())
OVERVIEW_SHA = '0876252ac7577c4b8af9f5d575daa3798d19c5b423331b273df52dda24707d9e'


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def build(suffix, stem):
    spec = json.loads(json.dumps(BASE))
    files = spec['files']
    frames = [json.loads(row) for row in files['video_frames.jsonl'].splitlines()]
    if len(frames) != 600:
        raise ValueError('Qualifier fixture needs 600 frame identities')
    qualifier = suffix.removesuffix('_near')
    context = {'format': 'c229397-native-qualifier-context-v1',
               'case_suffix': suffix, 'qualifier': qualifier,
               'traffic_actor_requested': stem == 'traffic',
               'device_requested': stem == 'device', 'device_actor_found': False,
               'law_instruction_source_required': stem == 'law',
               'officer_authority_source_required': stem == 'officer',
               'authority_and_necessity_unresolved': True,
               'diagnostic_fixture': True}
    files['qualifier-context.json'] = json.dumps(context, indent=2) + '\n'
    if stem == 'traffic':
        source_file = 'traffic-actors.jsonl'
        files[source_file] = ''.join(json.dumps({
            'video_frame': index, 'native_frame': frame['native_frame'],
            'actor_id': 22, 'vehicle_xy_m': [-16 + index * .02, -1.75],
            'speed_mps': .4}) + '\n' for index, frame in enumerate(frames))
        files['traffic_context_review.txt'] = 'Synthetic unresolved traffic necessity review\n'
        roles = {'participant_motion': source_file,
                 'traffic_context_review': 'traffic_context_review.txt'}
    elif stem == 'device':
        source_file = 'device-states.jsonl'
        files[source_file] = ''.join(json.dumps({
            'video_frame': index, 'native_frame': frame['native_frame'],
            'device_present': False, 'device_id': None, 'state': None}) + '\n'
            for index, frame in enumerate(frames))
        files['direction_context_review.txt'] = 'Synthetic unresolved device direction review\n'
        roles = {'device_identity': 'qualifier-context.json',
                 'device_state': source_file,
                 'direction_context_review': 'direction_context_review.txt'}
    else:
        source_file = 'authority-events.jsonl'
        files[source_file] = ''.join(json.dumps({
            'video_frame': index, 'native_frame': frame['native_frame'],
            'qualifier': qualifier, 'authority_status': 'unverified',
            'candidate_participant_id': 31 if stem == 'officer' else None}) + '\n'
            for index, frame in enumerate(frames))
        if stem == 'law':
            files['applicable_law_text.txt'] = 'Synthetic placeholder for independently sourced applicable law; not authority.\n'
            files['law_context_review.txt'] = 'Synthetic unresolved law applicability review.\n'
            roles = {'applicable_law_text': 'applicable_law_text.txt',
                     'law_context_review': 'law_context_review.txt',
                     'authority_timeline': source_file}
        else:
            files['officer_identity.txt'] = 'Synthetic candidate actor identity; police authority unverified.\n'
            files['officer_direction.txt'] = 'Synthetic candidate timed direction; no real officer instruction.\n'
            files['direction_context_review.txt'] = 'Synthetic unresolved officer direction review.\n'
            roles = {'officer_identity': 'officer_identity.txt',
                     'officer_direction': 'officer_direction.txt',
                     'direction_context_review': 'direction_context_review.txt',
                     'authority_timeline': source_file}
    roles.update(vehicle_poses='vehicle-poses.jsonl',
                 frame_map='video_frames.jsonl', overview_video='overview.mkv')
    packet = {'format': 'c229397-qualifier-source-packet-v1',
              'case_suffix': suffix, 'qualifier': qualifier,
              'finding': 'unresolved', 'diagnostic_fixture': True,
              'source_kind': 'synthetic_fixture', 'reviewed_video_frames': [200, 300],
              'sources': {role: {'path': rel, 'sha256': OVERVIEW_SHA if rel == 'overview.mkv'
                          else sha_bytes(files[rel].encode())} for role, rel in roles.items()}}
    files['qualifier-source-packet.json'] = json.dumps(packet, indent=2) + '\n'
    specification = HERE / ('diagnostic-qualifier-' + stem + '.json')
    specification.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    if specification.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic specification exceeds worker text limit')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(specification.relative_to(ROOT)),
                           'sha256': sha(specification)}],
              'generator': {'source': str(specification.relative_to(ROOT)),
                            'sha256': sha(specification)}}
    recipe_path = HERE / ('diagnostic-qualifier-' + stem + '-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    contract = {'format': 'worker-measurement-contract',
                'case_id': ASSIGNMENT + '__' + suffix,
                'requirements': [{'disposition_index': 0,
                                  'requirement': 'LVMC-11-52-130-A12',
                                  'source': 'LVMC 11.52.130(A)(12)',
                                  'output_key': 'qualifier_context',
                                  'method': 'measure_qualifier_context',
                                  'value_type': 'object', 'kind': 'sourced_context',
                                  'inputs': [source_file, 'qualifier-source-packet.json']}],
                'negative': {'remove': [source_file],
                             'error_contains': 'Missing required source: ' + source_file}}
    contract_path = PACKAGE / 'measurement-contracts' / (stem + '.json')
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(contract, indent=2) + '\n')
    return recipe_path, contract_path


def main():
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix, stem in (('traffic_conflict_near', 'traffic'),
                         ('law_compliance_near', 'law'),
                         ('police_direction_near', 'officer'),
                         ('device_direction_near', 'device')):
        recipe, contract = build(suffix, stem)
        entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + suffix))
        entry['fixture_recipe'] = str(recipe.relative_to(ROOT))
        entry['measurement_contract'] = str(contract.relative_to(PACKAGE))
    case_plan = {'requirement_dispositions': [
        {'requirement': 'LVMC-11-52-130-A12', 'source': 'LVMC 11.52.130(A)(12)',
         'branch': 'Diagnostic qualifier context, unresolved',
         'status': 'selected_required',
         'case_ids': [item['case_id'] for item in manifest['cases']]},
        {'requirement': 'LVMC-11-52-130-A12', 'source': 'LVMC 11.52.130(A)(12)',
         'branch': 'Textual exception applicability', 'status': 'exception_pending',
         'case_ids': []}]}
    (PACKAGE / 'case-plan.json').write_text(json.dumps(case_plan, indent=2) + '\n')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'recipes': ['diagnostic-qualifier-' + stem + '-recipe.json'
                                  for stem in ('traffic', 'law', 'officer', 'device')]}, sort_keys=True))


if __name__ == '__main__':
    main()
