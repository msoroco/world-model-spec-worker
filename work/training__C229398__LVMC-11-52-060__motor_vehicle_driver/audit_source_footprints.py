"""Independently join retained actor geometry to all selected derived footprints.

The selected CPU sources are synthetic diagnostics. This checks their data path,
not original Native geometry or physical acceptance.
"""
import hashlib
import json
import math
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
PARTS = ('vehicle', 'load', 'trailer')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def expected_vertices(actor):
    x, y = actor['center_xy_m']
    half_x, half_y = actor['half_extent_xy_m']
    if not all(math.isfinite(value) for value in (x, y, half_x, half_y)) or min(half_x, half_y) <= 0:
        raise ValueError('Invalid actor extent')
    yaw = math.radians(actor['yaw_deg'])
    cosine, sine = math.cos(yaw), math.sin(yaw)
    return [[x + dx * cosine - dy * sine, y + dx * sine + dy * cosine]
            for dx, dy in ((-half_x, -half_y), (half_x, -half_y),
                           (half_x, half_y), (-half_x, half_y))]


def check_rows(raw, derived, curb_sha):
    if len(raw) != len(derived) or len(raw) != 600:
        raise ValueError('Actor/footprint frame count differs')
    seen = {}
    for index, (source, footprint) in enumerate(zip(raw, derived)):
        if (source.get('frame') != index or footprint.get('frame') != index
                or source.get('source_kind') != 'synthetic_native_sample'
                or footprint.get('source_kind') != 'synthetic_native_sample'
                or footprint.get('curb_sha256') != curb_sha):
            raise ValueError('Actor/footprint frame identity differs at ' + str(index))
        actors, participants = source.get('actors'), footprint.get('participants')
        if not isinstance(actors, dict) or not isinstance(participants, dict) or set(actors) != set(PARTS) or set(participants) != set(PARTS):
            raise ValueError('Actor/footprint participant inventory differs at ' + str(index))
        vehicle_id = actors['vehicle']['actor_id']
        identities = set()
        for part in PARTS:
            actor, item = actors[part], participants[part]
            if actor is None or item is None:
                raise ValueError('Selected actor/footprint absent: ' + part + '/' + str(index))
            identity = actor['actor_id']
            if identity in identities or item.get('actor_id') != identity:
                raise ValueError('Actor/footprint identity differs: ' + part + '/' + str(index))
            identities.add(identity)
            if part != 'vehicle' and actor.get('attached_to') != vehicle_id:
                raise ValueError('Attachment differs: ' + part + '/' + str(index))
            vertices = item.get('vertices_xy_m')
            expected = expected_vertices(actor)
            if not isinstance(vertices, list) or len(vertices) != 4 or any(
                    not isinstance(actual, list) or len(actual) != 2 or any(
                        not math.isfinite(value) or abs(value - predicted) > 1e-7
                        for value, predicted in zip(actual, wanted))
                    for actual, wanted in zip(vertices, expected)):
                raise ValueError('Derived footprint differs: ' + part + '/' + str(index))
            previous = seen.setdefault(part, identity)
            if previous != identity:
                raise ValueError('Actor identity changed: ' + part + '/' + str(index))
    return seen


def main():
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = read(manifest_path)
    receipts = []
    for case in manifest['cases']:
        group = case['case_id'].rsplit('__', 1)[-1]
        for candidate in CANDIDATES:
            prefix = 'manifestbound-chain-' + group + '-' + candidate + '-'
            saved_path = PACKAGE / (prefix + 'saved.log')
            saved = read(saved_path)
            attempt = ROOT / '.runtime-work' / ('c229398-manifestbound-chain-' + group + '-' + candidate + '-compatibility')
            chain_path = PACKAGE / (prefix + 'proof.json')
            chain = read(chain_path)
            selected = case if candidate == 'primary' else next(item for item in case['candidates'] if item['id'] == candidate)
            raw_path = attempt / 'native-raw-actors.jsonl'
            footprints_path = attempt / 'derived-source-footprints.jsonl'
            curb_path = attempt / 'reviewed-curb.json'
            if (not chain['cpu_chain_passed'] or chain['selected_manifest_sha256'] != sha(manifest_path)
                    or saved['case_id'] != case['case_id'] or saved['candidate_id'] != candidate
                    or saved['native_revision']['construction_sha256'] != selected['construction_sha256']
                    or any(sha(path) != saved['original_source_hashes'][path.name]
                           for path in (raw_path, footprints_path, curb_path))):
                raise ValueError('Selected source binding differs: ' + group + '/' + candidate)
            raw, derived = rows(raw_path), rows(footprints_path)
            identities = check_rows(raw, derived, sha(curb_path))
            # Two independent negative controls prove that the join checks the
            # final retained frame and requires the selected load participant.
            altered = json.loads(json.dumps(derived))
            altered[-1]['participants']['trailer']['vertices_xy_m'][0][0] += 0.01
            try:
                check_rows(raw, altered, sha(curb_path))
            except ValueError as error:
                if not str(error).startswith('Derived footprint differs: trailer/599'):
                    raise
            else:
                raise ValueError('Altered final trailer footprint accepted')
            absent = json.loads(json.dumps(derived))
            absent[-1]['participants']['load'] = None
            try:
                check_rows(raw, absent, sha(curb_path))
            except ValueError as error:
                if not str(error).startswith('Selected actor/footprint absent: load/599'):
                    raise
            else:
                raise ValueError('Missing final load footprint accepted')
            receipts.append({'case_id': case['case_id'], 'candidate': candidate,
                             'selected_chain_sha256': sha(chain_path),
                             'raw_sha256': sha(raw_path),
                             'derived_sha256': sha(footprints_path),
                             'curb_sha256': sha(curb_path), 'frames_joined': 600,
                             'actor_ids': identities, 'negative_controls_rejected': 2})
    output = {'format': 'c229398-selected-footprint-source-join-v1',
              'selected_manifest_sha256': sha(manifest_path),
              'diagnostic_only': True, 'original_native_verified': False,
              'physical_acceptance_claimed': False,
              'selected_candidate_count': len(receipts), 'cases': receipts}
    path = PACKAGE / 'selected-footprint-source-join.json'
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'selected_candidates': len(receipts),
                      'negative_controls_rejected': 2 * len(receipts),
                      'receipt_sha256': sha(path)}))


if __name__ == '__main__':
    main()
