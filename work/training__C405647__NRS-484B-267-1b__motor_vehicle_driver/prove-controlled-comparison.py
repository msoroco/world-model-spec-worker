"""Exact synthetic reference/contrast controls for C405647 1(b)."""
import copy
import hashlib
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER / 'native'))
from prove_saved import packet

CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def rows_sha(rows):
    return sha_bytes(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows).encode())


def read(path):
    return json.loads(path.read_text())


def fixed(row):
    value = copy.deepcopy(row)
    value['subject']['center_xy_m'][1] = None
    for corner in value['subject']['body_xy_m']:
        corner[1] = None
    return value


def check_pair(reference, contrast):
    if len(reference) != len(contrast) or len(reference) != 480:
        raise ValueError('Controlled frame count differs')
    for a, b in zip(reference, contrast):
        if fixed(a) != fixed(b):
            raise ValueError('Controlled non-position source differs')
    if not any(a['subject']['center_xy_m'][1] != b['subject']['center_xy_m'][1]
               for a, b in zip(reference, contrast)):
        raise ValueError('Controlled edge intervention absent')


def prove():
    manifest_path = FOLDER / 'draft-execution-manifest.json'
    manifest = read(manifest_path)
    entries = {e['case_id'].rsplit('__', 1)[-1]: e for e in manifest['cases']}
    assert set(entries) == set(CASES)
    result = []
    negatives = []
    for candidate in CANDIDATES:
        packets = {case: packet(case, candidate) for case in CASES}
        ref_scope, reference = packets['reference']
        contrast_scope, contrast = packets['contrast']
        assert {k: v for k, v in ref_scope.items() if k != 'case_suffix'} == {
            k: v for k, v in contrast_scope.items() if k != 'case_suffix'}
        check_pair(reference, contrast)
        bindings = {}
        measured = {}
        for case, (scope, rows) in packets.items():
            entry = entries[case]
            candidate_ref = entry if candidate == 'primary' else next(
                x for x in entry['candidates'] if x['id'] == candidate)
            construction = FOLDER / candidate_ref['construction']
            assert sha_bytes(construction.read_bytes()) == candidate_ref['construction_sha256']
            analysis_path = FOLDER / 'draft-candidates' / case / candidate / 'finalization-analysis.json'
            analysis = read(analysis_path)
            assert analysis['case_id'] == entry['case_id']
            value = analysis['measurements']['right_edge_geometry']['value']
            assert value['actor_frames_sha256'] == rows_sha(rows)
            assert value['source_kind'] == 'synthetic_cpu' and value['frames'] == 480
            assert value['vehicle_authority_or_lamps_qualified'] is False
            assert value['legal_immediacy_or_edge_verdict'] is None
            assert analysis['physical_acceptance_claimed'] is False
            bindings[case] = {'construction_sha256': candidate_ref['construction_sha256'],
                              'analysis_sha256': sha_bytes(analysis_path.read_bytes()),
                              'actor_frames_sha256': rows_sha(rows)}
            measured[case] = {'edge_frame': value['first_edge_target_frame'],
                              'catchup_frame': value['approach_catchup_frame'],
                              'stop_frame': value['first_ten_frame_stop'],
                              'stop_center_xy_m': value['stop_center_xy_m']}
        assert measured['reference']['edge_frame'] is not None
        assert measured['reference']['edge_frame'] < measured['reference']['catchup_frame']
        assert measured['contrast']['edge_frame'] is None
        assert measured['reference']['catchup_frame'] == measured['contrast']['catchup_frame']
        assert measured['reference']['stop_frame'] == measured['contrast']['stop_frame']
        result.append({'candidate': candidate, 'bindings': bindings, 'measured': measured,
                       'fixed_rows': 480, 'changed_field': 'subject lateral position and body footprint'})
        for name, mutation in (
            ('approach', lambda r: r[75]['approach']['center_xy_m'].__setitem__(0, 999.0)),
            ('speed', lambda r: r[75]['subject'].__setitem__('speed_mps', 99.0)),
            ('frame', lambda r: r[75].__setitem__('native_frame', 9999)),
            ('body_x', lambda r: r[75]['subject']['body_xy_m'][0].__setitem__(0, 999.0)),
        ):
            bad = copy.deepcopy(contrast)
            mutation(bad)
            try:
                check_pair(reference, bad)
            except ValueError as exc:
                if str(exc) != 'Controlled non-position source differs':
                    raise
            else:
                raise AssertionError('Changed controlled field accepted')
            negatives.append({'candidate': candidate, 'mutation': name,
                              'actor_frames_sha256': rows_sha(bad),
                              'rejection': 'Controlled non-position source differs'})
    proof = {'format': 'c405647-1b-synthetic-controlled-comparison-v1',
             'manifest_sha256': sha_bytes(manifest_path.read_bytes()),
             'pairs': result, 'negative_mutations': negatives,
             'original_authority_or_lamps_observed': False,
             'legal_or_delivery_acceptance': False}
    (FOLDER / 'synthetic-controlled-comparison.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    proof = prove()
    print(f"{len(proof['pairs'])} controlled pairs; {len(proof['negative_mutations'])} negatives")
