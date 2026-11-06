"""Independent audit of retained synthetic saved positives and negatives."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def source_hashes(folder):
    return {str(path.relative_to(folder)):sha(path) for path in folder.rglob('*')
            if path.is_file() and path.name not in ('result.json','analysis-report.json')}


def inspect(record):
    root = Path(record['retained_positive'])
    assert root.is_relative_to(ROOT/'.runtime-work') and root.is_dir()
    assert source_hashes(root) == record['original_source_hashes']
    assert sha(root/'analysis-report.json') == record['analysis_report_sha256']
    assert sha(root/'result.json') == record['result_sha256']
    samples = rows(root/'native_samples.jsonl')
    trace, evidence, mapping, frames = (rows(root/name) for name in
        ('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl','capture/native/frames.jsonl'))
    assert len(samples) == len(trace) == len(evidence) == len(mapping) == len(frames) == 900
    report = json.loads((root/'analysis-report.json').read_text())
    result = json.loads((root/'result.json').read_text())
    measured = report['measurements']['moving_following_interval']
    assert measured['sources'] == {'native_samples.jsonl':sha(root/'native_samples.jsonl'),
                                   'following_context.json':sha(root/'following_context.json')}
    gaps = []
    for i, (sample, t, e, m, f) in enumerate(zip(samples,trace,evidence,mapping,frames)):
        frame, time = 100+i, (i+1)/20
        assert sample['native_frame'] == t['frame'] == e['original_frame'] == m['native_frame'] == f['frame'] == frame
        assert m['video_frame'] == i and m['carla_frame'] == frame
        assert all(abs(row_time-time)<1e-9 for row_time in
                   (sample['time_s'],t['time_s'],e['recording_time_s'],m['time_s']))
        assert e['synthetic_diagnostic'] is True and t['synthetic_diagnostic'] is True
        ego, lead = sample['ego'], sample['lead']
        assert ego['native_road_id'] == lead['native_road_id'] == 1
        assert ego['native_lane_id'] == lead['native_lane_id'] == -1
        assert ego['speed_mps'] == lead['speed_mps'] == 8
        observed_body = {(round(p[0],3),round(p[1],3)) for p in e['ego']['body_vertices_m']}
        expected_body = {(round(p[0],3),round(p[1],3)) for p in ego['native_body_xy_m']}
        assert observed_body == expected_body and len(observed_body) == 4
        gaps.append(min(p[0] for p in lead['native_body_xy_m'])-
                    max(p[0] for p in ego['native_body_xy_m']))
    assert measured['value']['median_bumper_gap_m'] == round(statistics.median(gaps),6)
    assert measured['value']['median_time_headway_s'] == round(statistics.median(gaps)/8,6)
    assert result['measured_values']['median_bumper_gap_m'] == round(statistics.median(gaps),6)
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert result['setup_confirmed'] is False
    assert result['behavior_attempted'] is False and result['maneuver_completed'] is False
    assert result['provenance_kind'] == 'synthetic_local_diagnostic'
    assert report['original_joins']['frames'] == 900
    assert set(report['video_frames'].values()) == {900}
    for camera in ('overview','approach','reference_corner','driver_reference'):
        probe = subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',
            str(root/(camera+'.mkv'))],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=120)
        assert probe.returncode == 0 and probe.stdout.strip() == '900'
    missing, wrong = Path(record['retained_missing']), Path(record['retained_wrong_lane'])
    assert not (missing/'native_samples.jsonl').exists()
    assert rows(wrong/'native_samples.jsonl')[10]['lead']['native_lane_id'] == 1
    assert not (missing/'result.json').exists() and not (wrong/'result.json').exists()
    return samples, json.loads((root/'following_context.json').read_text()), result


def main():
    os.environ['PATH'] = str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    summary = json.loads((HERE/'saved-following-summary.json').read_text())
    assert summary['format'] == 'c102304-retained-synthetic-saved-proof-v1'
    assert len(summary['records']) == 2
    first, first_context, result_a = inspect(summary['records'][0])
    second, second_context, result_b = inspect(summary['records'][1])
    assert first_context == second_context
    assert result_a['measured_values']['median_bumper_gap_m'] == 10
    assert result_b['measured_values']['median_bumper_gap_m'] == 25
    for a,b in zip(first,second):
        assert a['ego'] == b['ego']
        assert a['native_frame'] == b['native_frame'] and a['time_s'] == b['time_s']
        for pa,pb in zip(a['lead']['native_body_xy_m'],b['lead']['native_body_xy_m']):
            assert abs(pb[0]-pa[0]-15)<1e-9 and pa[1] == pb[1]
    print(json.dumps({'audit':'pass','paired_frames':900,'source_videos':8,
                      'exact_source_hashes':True,'negative_fixtures':4,
                      'accepted_recordings':0},sort_keys=True))


if __name__ == '__main__':
    main()
