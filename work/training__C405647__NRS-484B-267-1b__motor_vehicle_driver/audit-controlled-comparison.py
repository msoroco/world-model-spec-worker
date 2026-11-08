"""Independently reconstruct all saved comparison sources and controls."""
import copy
import hashlib
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER / 'native'))
from prove_saved import packet


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_hash(rows):
    payload = ''.join(json.dumps(item, sort_keys=True) + '\n' for item in rows)
    return hashlib.sha256(payload.encode()).hexdigest()


def fixed_fields(row):
    subject = row['subject']
    return (row['frame'], row['native_frame'], row['video_frame'], row['time_s'],
            row['coordinate_frame'], row['source_kind'], row['approach'],
            subject['center_xy_m'][0], subject['heading_deg'], subject['speed_mps'],
            tuple(point[0] for point in subject['body_xy_m']))


def rejected(reference, contrast):
    return any(fixed_fields(a) != fixed_fields(b) for a, b in zip(reference, contrast))


proof = json.loads((FOLDER / 'synthetic-controlled-comparison.json').read_text())
manifest_path = FOLDER / 'draft-execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
assert proof['manifest_sha256'] == sha(manifest_path)
assert len(proof['pairs']) == 4 and len(proof['negative_mutations']) == 16
entries = {entry['case_id'].rsplit('__', 1)[-1]: entry for entry in manifest['cases']}
assert set(entries) == {'reference', 'contrast'}
negative_index = {(x['candidate'], x['mutation']): x for x in proof['negative_mutations']}
assert len(negative_index) == 16
rows = []
for pair in proof['pairs']:
    candidate = pair['candidate']
    packets = {case: packet(case, candidate) for case in ('reference', 'contrast')}
    reference = packets['reference'][1]
    contrast = packets['contrast'][1]
    assert len(reference) == len(contrast) == pair['fixed_rows'] == 480
    assert not rejected(reference, contrast)
    assert packets['reference'][0]['assignment_sha256'] == packets['contrast'][0]['assignment_sha256']
    assert packets['reference'][0]['source_kind'] == packets['contrast'][0]['source_kind'] == 'synthetic_cpu'
    for case in ('reference', 'contrast'):
        entry = entries[case]
        ref = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
        construction_path = FOLDER / ref['construction']
        analysis_path = FOLDER / 'draft-candidates' / case / candidate / 'finalization-analysis.json'
        analysis = json.loads(analysis_path.read_text())
        binding = pair['bindings'][case]
        assert binding['construction_sha256'] == ref['construction_sha256'] == sha(construction_path)
        assert binding['analysis_sha256'] == sha(analysis_path)
        assert binding['actor_frames_sha256'] == row_hash(packets[case][1])
        assert analysis['measurements']['right_edge_geometry']['value']['actor_frames_sha256'] == binding['actor_frames_sha256']
        assert analysis['selected'] is False and analysis['legal_verdict_claimed'] is False
        assert analysis['physical_acceptance_claimed'] is False
        measured = pair['measured'][case]
        xs = packets[case][1]
        edge = next((r['frame'] for r in xs if r['subject']['center_xy_m'][1] <= -5.95 and
                     min(p[1] for p in r['subject']['body_xy_m']) >= -7), None)
        catchup = next((r['frame'] for r in xs if r['subject']['center_xy_m'][0] -
                        r['approach']['center_xy_m'][0] <= 4.5), None)
        stop = next((i for i in range(471) if max(x['subject']['speed_mps'] for x in xs[i:i+10]) <= .1), None)
        assert measured == {'edge_frame': edge, 'catchup_frame': catchup,
                            'stop_frame': stop,
                            'stop_center_xy_m': xs[stop]['subject']['center_xy_m']}
        assert analysis['measurements']['right_edge_geometry']['value']['first_edge_target_frame'] == edge
    assert pair['measured']['reference']['edge_frame'] < pair['measured']['reference']['catchup_frame']
    assert pair['measured']['contrast']['edge_frame'] is None
    assert pair['measured']['reference']['catchup_frame'] == pair['measured']['contrast']['catchup_frame']
    assert pair['measured']['reference']['stop_frame'] == pair['measured']['contrast']['stop_frame']
    for name in ('approach', 'speed', 'frame', 'body_x'):
        bad = copy.deepcopy(contrast)
        if name == 'approach': bad[75]['approach']['center_xy_m'][0] = 999.0
        elif name == 'speed': bad[75]['subject']['speed_mps'] = 99.0
        elif name == 'frame': bad[75]['native_frame'] = 9999
        else: bad[75]['subject']['body_xy_m'][0][0] = 999.0
        negative = negative_index[(candidate, name)]
        assert negative['actor_frames_sha256'] == row_hash(bad)
        assert negative['rejection'] == 'Controlled non-position source differs'
        assert rejected(reference, bad)
    rows.append({'candidate': candidate,
                 'reference_edge_frame': pair['measured']['reference']['edge_frame'],
                 'contrast_edge_frame': None,
                 'catchup_frame': pair['measured']['reference']['catchup_frame']})
assert proof['original_authority_or_lamps_observed'] is False
assert proof['legal_or_delivery_acceptance'] is False
out = {'format': 'c405647-1b-independent-controlled-comparison-audit-v1',
       'manifest_sha256': sha(manifest_path), 'comparison_sha256': sha(FOLDER / 'synthetic-controlled-comparison.json'),
       'pairs': rows, 'negative_count': 16, 'scope': 'synthetic_cpu',
       'original_or_legal_result_proven': False}
(FOLDER / 'synthetic-controlled-comparison-audit.json').write_text(json.dumps(out, indent=2) + '\n')
print('independent comparison audit: 4 pairs, 16 source mutations')
