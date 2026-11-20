"""Independently compare retained fire-lane attempts without a legal verdict."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from source_measurement import analyze, camera_sources, read_lines, sha

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selection(case, attempt, result_path):
    attempt = Path(attempt)
    result_path = Path(result_path)
    manifest = read(HERE/f'draft-{case}-fallback-manifest.json')
    entry = manifest['cases'][0]
    selected = read(attempt/'candidate-selection.json')
    result = read(result_path)
    analysis_report = read(result_path.parent/'analysis-report.json')
    require(entry['case_id'] == ASSIGNMENT+'__'+case and
            selected['case_id'] == entry['case_id'] and
            selected['candidate_id'] == 'primary' and
            selected['construction_sha256'] == entry['construction_sha256'] and
            result['case_id'] == entry['case_id'],
            'Comparison exact primary selection differs: '+case)
    construction = read(HERE/entry['construction'])
    require(sha(HERE/entry['construction']) == entry['construction_sha256'],
            'Comparison construction hash differs: '+case)
    config = json.loads(next(row['content'] for row in construction['files']
                             if row['path'] == 'config.json'))
    require(config['case_id'] == entry['case_id'] and
            config['candidate_id'] == 'primary' and
            config['case_suffix'] == case and
            config['comparison_requested_value'] is (case == 'reference') and
            (config['frames'], config['rate_hz'], config['duration_s']) == (600, 20, 30),
            'Comparison config differs: '+case)
    provenance = read(attempt/'acquisition-provenance.json')
    diagnostic = provenance.get('provenance_kind') == 'synthetic_fixture'
    require(diagnostic == (result['provenance_kind'] == 'synthetic_fixture') and
            result['diagnostic_fixture'] is diagnostic and
            not result['accepted'] and not result['physical_acceptance_claimed'] and
            not result['legal_verdict_claimed'],
            'Comparison provenance or acceptance differs: '+case)
    require(analysis_report['case_id'] == entry['case_id'] and
            analysis_report['provenance_kind'] == result['provenance_kind'],
            'Comparison saved report identity differs: '+case)
    for relative, checksum in analysis_report['source_sha256'].items():
        require(sha(result_path.parent/relative) == checksum and
                sha(attempt/relative) == checksum,
                'Comparison saved source hash differs: '+case+'/'+relative)
    measured = analyze(attempt, case, diagnostic=diagnostic)
    cameras = camera_sources(attempt, measured['frames'])
    require(measured['frames'] == 600 and set(cameras) == set(CAMERAS),
            'Comparison frame or camera sources differ: '+case)
    expected = result['measured_values']
    require(expected['near_zero_with_authored_zone_overlap_frames'] ==
            measured['near_zero_with_zone_overlap_frames'] and
            expected['near_zero_disjoint_from_authored_zone_frames'] ==
            measured['near_zero_disjoint_frames'],
            'Saved measurement differs from retained sources: '+case)
    require(result['target_checks'][0]['requested'] is (case == 'reference') and
            result['target_checks'][0]['matched'] is True,
            'Comparison sampled target not met: '+case)
    return {'attempt': attempt, 'result': result, 'result_path': result_path,
            'config': config, 'measured': measured, 'cameras': cameras,
            'diagnostic': diagnostic, 'survey': read(attempt/'native-survey-readback.json'),
            'actors': read_lines(attempt/'native-actors.jsonl'),
            'frames': read_lines(attempt/'video_frames.jsonl'),
            'selection_sha256': sha(attempt/'candidate-selection.json')}


def frame_digest(path):
    command = ['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0',
               '-f', 'framemd5', '-']
    run = subprocess.run(command, capture_output=True, text=True)
    require(run.returncode == 0, 'Comparison source-camera decode failed: '+str(path))
    rows = [line for line in run.stdout.splitlines() if line and not line.startswith('#')]
    require(len(rows) == 600, 'Comparison decoded frame count differs: '+str(path))
    return hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest()


def audit(left_attempt, left_result, right_attempt, right_result):
    plan = read(HERE/'case-plan.json')
    spec = next(row for row in plan['comparisons'] if row['comparison_id'] ==
                ASSIGNMENT+'__comparison_main')
    require(spec['case_ids'] == [ASSIGNMENT+'__reference', ASSIGNMENT+'__contrast'] and
            spec['deliberate_differences'] == ['vehicle_stops_in_posted_fire_lane'],
            'Comparison plan differs')
    ref = selection('reference', left_attempt, left_result)
    con = selection('contrast', right_attempt, right_result)
    require(ref['diagnostic'] == con['diagnostic'],
            'Comparison provenance kinds differ')
    for key in ('assignment_id', 'law_id', 'cell_id', 'actor', 'rate_hz',
                'frames', 'duration_s', 'cameras', 'recording_description',
                'survey_contract', 'comparison_variable'):
        require(ref['config'][key] == con['config'][key],
                'Comparison changed fixed config: '+key)
    for key in ('map_name', 'capture_frames', 'capture_hz', 'camera_names',
                'survey_geometry', 'fixed_context'):
        require(ref['survey'][key] == con['survey'][key],
                'Comparison changed surveyed context: '+key)
    require(ref['frames'] == con['frames'] and
            all(a['time_s'] == b['time_s'] for a,b in zip(ref['frames'], con['frames'])),
            'Comparison source clocks differ')
    require(ref['measured']['near_zero_with_zone_overlap_frames'] > 0 and
            con['measured']['near_zero_disjoint_frames'] > 0 and
            con['measured']['near_zero_with_zone_overlap_frames'] == 0,
            'Comparison sampled stop relation absent')
    camera_digests = {}
    for name in CAMERAS:
        a = ref['cameras'][name]
        b = con['cameras'][name]
        require((a['width'], a['height'], a['decoded_frames']) ==
                (b['width'], b['height'], b['decoded_frames']),
                'Comparison camera profile differs: '+name)
        if ref['diagnostic']:
            a_hash = frame_digest(ref['attempt']/(name+'.mkv'))
            b_hash = frame_digest(con['attempt']/(name+'.mkv'))
            require(a_hash == b_hash,
                    'Synthetic fixed-camera decoded frames differ: '+name)
            camera_digests[name] = a_hash
    if ref['diagnostic']:
        for index,(a,b) in enumerate(zip(ref['actors'],con['actors'])):
            shifted = json.loads(json.dumps(a))
            shifted['ego_pose_xyz_m'][0] += 14
            for field in ('ego_body_vertices_xyz_m','following_body_vertices_xyz_m'):
                for vertex in shifted[field]: vertex[0] += 14
            require(shifted == b,
                    'Synthetic comparison changed another actor field at '+str(index))
    return {'format': 'c201084-fire-lane-comparison-audit',
            'comparison_id': spec['comparison_id'], 'passed': True,
            'diagnostic_only': ref['diagnostic'], 'accepted': False,
            'source_cases': spec['case_ids'],
            'reference_selection_sha256': ref['selection_sha256'],
            'contrast_selection_sha256': con['selection_sha256'],
            'reference_result_sha256': sha(ref['result_path']),
            'contrast_result_sha256': sha(con['result_path']),
            'sampled_reference_overlap_frames': ref['measured']['near_zero_with_zone_overlap_frames'],
            'sampled_contrast_disjoint_frames': con['measured']['near_zero_disjoint_frames'],
            'decoded_fixed_camera_sha256': camera_digests,
            'original_posting_verified': False, 'legal_verdict_claimed': False,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('reference_attempt', 'reference_result', 'contrast_attempt',
                 'contrast_result', 'output'):
        parser.add_argument('--'+name.replace('_','-'), type=Path, required=True)
    args = parser.parse_args()
    outcome = audit(args.reference_attempt, args.reference_result,
                    args.contrast_attempt, args.contrast_result)
    require(not args.output.exists(), 'Retain previous comparison audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'passed': outcome['passed'],
                      'diagnostic_only': outcome['diagnostic_only'],
                      'comparison_id': outcome['comparison_id']}, sort_keys=True))
