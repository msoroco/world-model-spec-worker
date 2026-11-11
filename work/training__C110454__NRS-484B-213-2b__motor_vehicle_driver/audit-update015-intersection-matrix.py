"""Independently bind current exact receipts to the raw synthetic approach pair."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def lines(source):
    return [json.loads(line) for line in source.splitlines() if line.strip()]


def audit(index=None):
    index = index or json.loads((HERE/'update015-intersection-proof-index.json').read_text())
    require(index['selected'] is False and index['physical_acceptance_claimed'] is False,
            'False physical selection')
    require(index['compatibility_passed'] == index['process_saved_passed'] == 8 and
            len(index['cases']) == 2, 'Exact matrix incomplete')
    manifest_path = HERE/'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    require(manifest['runtime_manifest_sha256'] == sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json'),
            'Runtime source changed')
    case_map = {item['case_id']: item for item in manifest['cases']}
    relations = {}
    joined = 0
    for suffix, case_row in zip(('reference', 'contrast'), index['cases']):
        case_id = HERE.name+'__'+suffix
        require(case_row['case_id'] == case_id and case_id in case_map, 'Case binding changed')
        construction = case_map[case_id]
        candidates = [{'id': 'primary', 'construction': construction['construction'],
                       'construction_sha256': construction['construction_sha256']}]+construction['candidates']
        require([row['id'] for row in candidates] == list(CANDIDATES), 'Candidate inventory changed')
        require([row['candidate_id'] for row in case_row['candidates']] == list(CANDIDATES),
                'Exact candidate proofs missing')
        require(len({row['construction_sha256'] for row in candidates}) == 4,
                'Candidate constructions duplicate')
        triggers = {(row['trigger']['source'], row['trigger']['metric'],
                     row['trigger']['failure_condition']) for row in candidates[1:]}
        require(len(triggers) == 3, 'Fallback triggers duplicate')
        spec_path = HERE/f'update015-{suffix}-diagnostic.json'
        recipe_path = HERE/f'update015-{suffix}-recipe.json'
        recipe = json.loads(recipe_path.read_text())
        require(recipe['sources'][0]['sha256'] == sha(spec_path), 'Recipe source differs')
        spec = json.loads(spec_path.read_text())
        require([v['path'] for v in spec['videos']] == [c+'.mkv' for c in CAMERAS] and
                all(v['frames'] == 480 for v in spec['videos']), 'Camera recipe differs')
        samples = lines(spec['files']['native_samples.jsonl'])
        frames = lines(spec['files']['video_frames.jsonl'])
        body = lines(spec['files']['body_history.jsonl'])
        trace = lines(spec['files']['trace.jsonl'])
        evidence = lines(spec['files']['capture/evidence.jsonl'])
        native = lines(spec['files']['capture/native/frames.jsonl'])
        require(all(len(rows) == 480 for rows in (samples, frames, body, trace, evidence, native)),
                'Raw frame inventory incomplete')
        left = []
        for i, (sample, frame, body_row, trace_row, ev, native_row) in enumerate(
                zip(samples, frames, body, trace, evidence, native)):
            require(sample['video_frame'] == frame['video_frame'] == i and
                    sample['native_frame'] == frame['native_frame'] == native_row['frame'] and
                    abs(sample['time_s']-frame['time_s']) < 1e-6 and
                    abs(sample['time_s']-trace_row['time_s']) < 1e-6 and
                    sample['native_body_xy_m'] == sample['body_xy_m'] and
                    body_row['frame'] == sample['native_frame'] and
                    abs(body_row['time_s']-sample['time_s']) < 1e-6 and
                    trace_row['frame'] == sample['native_frame'] and
                    trace_row['speed_mps'] == sample['speed_m_s'] and
                    ev['original_frame'] == sample['native_frame'] and
                    abs(ev['recording_time_s']-sample['time_s']) < 1e-6 and
                    ev['ego']['speed_mps'] == sample['speed_m_s'] and
                    abs(native_row['time_s']-sample['time_s']) < 1e-6 and
                    sample['speed_provenance'] == 'synthetic_native_sample' and
                    sample['two_way_native_survey'] is True and
                    ev['ego']['body_vertices_m'], 'Raw join or provenance differs')
            corners = sample['body_xy_m']
            if min(p[1] for p in corners) > 0 and max(p[0] for p in corners) < -7 and sample['speed_m_s'] > .05:
                left.append(-7-max(p[0] for p in corners))
            joined += 1
        require(left, 'No synthetic left-side approach interval')
        nearest = min(left)
        relation = 'within_100_ft' if nearest < 30.48 else 'outside_100_ft'
        relations[suffix] = relation
        for expected, proof in zip(candidates, case_row['candidates']):
            folder = HERE/'update015-intersection-proofs'/suffix/expected['id']
            compat = json.loads((folder/'compatibility.json').read_text())
            saved = json.loads((folder/'process-saved.json').read_text())
            require(proof['case_id'] == case_id and proof['candidate_id'] == expected['id'] and
                    proof['selected'] is False and proof['synthetic_diagnostic'] is True and
                    proof['manifest_sha256'] == sha(manifest_path) and
                    proof['recipe_sha256'] == sha(recipe_path) and
                    proof['construction_sha256'] == sha(HERE/expected['construction']) == expected['construction_sha256'] and
                    proof['compatibility_sha256'] == sha(folder/'compatibility.json') and
                    proof['process_saved_sha256'] == sha(folder/'process-saved.json') and
                    proof['compatibility_log_sha256'] == sha(folder/'compatibility.log') and
                    proof['process_saved_log_sha256'] == sha(folder/'process-saved.log'),
                    'Exact receipt binding differs')
            measured = compat['measurement_examples']['intersection_approach_relation']['value']
            require(compat['passed'] is True and compat['negative_removed'] == 'native_samples.jsonl' and
                    compat['fixture_manifest']['diagnostic-input.json'] == sha(spec_path) and
                    measured['sampled_relation'] == relation and
                    abs(measured['nearest_body_front_to_intersection_m']-nearest) < 1e-5 and
                    measured['legal_verdict'] is None and
                    saved['passed'] is True and saved['originals_preserved'] is True and
                    saved['timestamp_joins']['frames'] == 480 and
                    saved['final_video_checks']['passed'] is True and
                    saved['final_video_checks']['frames'] == 480 and
                    saved['missing_evidence'] is False and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Exact receipt lacks required proof')
    require(relations == {'reference':'outside_100_ft','contrast':'within_100_ft'},
            'Boundary contrast differs')
    return {'raw_frame_joins_checked':joined,'exact_compatibility_passed':8,
            'exact_process_saved_passed':8,'relations':relations,'selected':False}


if __name__ == '__main__':
    result = audit()
    original = json.loads((HERE/'update015-intersection-proof-index.json').read_text())
    rejected = 0
    for damage in ('missing_candidate', 'false_selection', 'wrong_receipt'):
        altered = copy.deepcopy(original)
        if damage == 'missing_candidate': altered['cases'][0]['candidates'].pop()
        elif damage == 'false_selection': altered['selected'] = True
        else: altered['cases'][0]['candidates'][0]['compatibility_sha256'] = '0'*64
        try: audit(altered)
        except (ValueError, KeyError): rejected += 1
        else: raise ValueError('Damaged exact matrix accepted')
    result['isolated_negative_rejections'] = rejected
    print(json.dumps(result, sort_keys=True))
