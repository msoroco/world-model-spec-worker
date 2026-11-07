"""Recompute retained official-branch synthetic saved evidence independently."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FFPROBE = REPO / '.runtime-work/linux_arm64/ffprobe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    proof = json.loads((HERE / 'saved-proof.json').read_text())
    assert proof['passed'] and proof['source_kind'] == 'synthetic_cpu'
    assert len(proof['results']) == 8 and FFPROBE.is_file()
    seen = set()
    for item in proof['results']:
        case = item['case_id'].rsplit('__', 1)[1]
        candidate = item['candidate_id']
        assert case in ('official_1', 'official_2')
        assert candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')
        assert (case, candidate) not in seen
        seen.add((case, candidate))
        folder = HERE / 'saved-fixtures' / case / candidate
        config = json.loads((folder / 'config.json').read_text())
        report = json.loads((folder / 'analysis-report.json').read_text())
        result = json.loads((folder / 'result.json').read_text())
        scope = json.loads((folder / 'source-scope.json').read_text())
        assert item['analysis_report_sha256'] == sha(folder / 'analysis-report.json')
        assert item['result_sha256'] == sha(folder / 'result.json')
        assert item['negative_log_sha256'] == sha(folder / 'negative-analysis.log')
        assert 'Missing required source: source-scope.json' in (folder / 'negative-analysis.log').read_text()
        assert scope['case_suffix'] == case and scope['source_kind'] == 'synthetic_cpu'
        assert scope['vehicle_authority_verified'] is False
        assert scope['front_red_lamp_qualification_verified'] is False
        for name, expected in scope['native_source_hashes'].items():
            assert sha(folder / name) == expected
        native = rows(HERE / 'drafts' / case / candidate / 'native-requests.jsonl')
        raw = rows(folder / 'observed-actors.jsonl')
        saved = rows(folder / 'actor-frames.jsonl')
        mapping = rows(folder / 'video_frames.jsonl')
        trace = rows(folder / 'trace.jsonl')
        assert len(native) == len(raw) == len(saved) == len(mapping) == len(trace) == 480
        gap, clear, lamps = [], [], []
        for index, (request, actor, row, video, point) in enumerate(
                zip(native, raw, saved, mapping, trace)):
            assert row['frame'] == actor['frame'] == video['video_frame'] == index
            assert row['native_frame'] == actor['native_frame'] == video['native_frame'] == video['carla_frame'] == point['frame']
            assert abs(row['time_s'] - index / 20) < 1e-5
            subject, approach = request['subject_request'], request['approach_request']
            assert actor['actors']['subject']['native_center_xy_m'] == [subject['x_m'], subject['y_m']]
            assert actor['actors']['approach']['native_center_xy_m'] == [approach['x_m'], approach['y_m']]
            assert row['subject'] == {'x_m': subject['x_m'], 'y_m': -subject['y_m']}
            assert row['approach'] == {'x_m': approach['x_m'], 'y_m': -approach['y_m']}
            assert row['front_red_flash_on'] == request['lamp_request']['front_red_flash_on']
            gap.append(row['subject']['x_m'] - row['approach']['x_m'])
            clear.append(max(vertex[1] for vertex in row['subject_body_xy_m']) < -3.5)
            lamps.append(row['front_red_flash_on'])
        catchup = next((i for i, value in enumerate(gap) if value <= 4.5), None)
        clearance = next((i for i, value in enumerate(clear) if value), None)
        measured = report['measurements']['official_approach_clearance']['value']
        assert measured['catchup_frame'] == catchup
        assert measured['first_full_body_inner_lane_clearance_frame'] == clearance
        assert measured['observed_lamp_transitions'] == sum(a != b for a, b in zip(lamps, lamps[1:]))
        assert measured['vehicle_authority_verified'] is False
        assert measured['lamp_qualification_verified'] is False
        assert measured['legal_immediacy_or_yield_verdict'] is None
        assert config['case_id'] == item['case_id'] and result['case_id'] == item['case_id']
        assert result['accepted'] is False and result['setup_confirmed'] is False
        assert result['target_checks'][0]['requested'] == (case == 'official_1')
        for channel in result['recording_evidence']:
            assert len(rows(folder / channel['reference'])) == 480
        for video in result['video_references']:
            probe = subprocess.run([str(FFPROBE), '-v', 'error', '-count_frames',
                                    '-select_streams', 'v:0', '-show_entries',
                                    'stream=nb_read_frames,width,height', '-of', 'json',
                                    str(folder / video)], check=True, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            stream = json.loads(probe.stdout)['streams'][0]
            assert int(stream['nb_read_frames']) == 480
    return {'passed': True, 'retained_case_candidates': len(seen),
            'source_hashes_recomputed': True, 'four_videos_each_decoded': True,
            'original_pixels_or_native_verified': False,
            'portable_core_lean_compatibility_verified': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
