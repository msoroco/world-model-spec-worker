"""Independent exact-case source and delivery audit; no legal acceptance claim."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(case, attempt):
    attempt = Path(attempt)
    required = ['original_bridge_survey.json', 'bridge-native.jsonl', 'trace.jsonl',
                'video_frames.jsonl', 'acquisition-provenance.json', 'capture/evidence.jsonl',
                'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv',
                'result.json', 'bridge-findings.json', 'event_review.webm', 'final-decode.json']
    for name in required:
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    survey = json.loads((attempt / 'original_bridge_survey.json').read_text())
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    require(survey.get('assignment_id') == case.rsplit('__', 1)[0], 'Wrong original bridge survey assignment')
    require(survey.get('source_kind') in ('synthetic_native_sample', 'original_native_bridge_survey'), 'Bridge survey source kind missing')
    authority = survey.get('administrative_declaration', {})
    for key in ('department_source_id', 'investigation_source_id', 'finding_source_id',
                'declaration_source_id', 'otherwise_permissible_speed_source_id'):
        require(authority.get(key), 'Original DOT authority source missing: ' + key)
    maximum = authority.get('safe_maximum_mph')
    ordinary = authority.get('otherwise_permissible_speed_mph')
    require(type(maximum) in (int, float) and type(ordinary) in (int, float) and
            math.isfinite(maximum) and math.isfinite(ordinary) and 0 < maximum < ordinary,
            'Original DOT maximum and finding relation missing')
    for key in ('highway_source_id', 'chapter_408_source_id', 'structure_source_id', 'structure_polygon_xy_m'):
        require(survey.get(key), 'Original bridge source missing: ' + key)
    signs = survey.get('signs', [])
    require(len(signs) == 2 and {sign.get('end') for sign in signs} == {'first', 'second'},
            'Original advance signs at each end missing')
    for sign in signs:
        require(sign.get('maximum_mph') == maximum and sign.get('instruction_kind') == 'structure_maximum'
                and sign.get('distance_before_end_ft') == 100,
                'Original structural sign maximum or 100-foot placement missing')
        for key in ('source_id', 'department_authorization_source_id', 'maintained_source_id',
                    'governed_approach_source_id', 'visible_instruction_source_id',
                    'position_xyz_m', 'structure_end_xyz_m'):
            require(sign.get(key), 'Original sign source missing: ' + key)
    trace = records(attempt / 'bridge-native.jsonl')
    frames = records(attempt / 'video_frames.jsonl')
    source_trace = records(attempt / 'trace.jsonl')
    require(len(trace) == len(frames) == len(source_trace) == 600, 'Original 600-frame source join missing')
    require(all(t.get('frame') == i and m.get('video_frame') == i and
                t.get('native_frame') == m.get('native_frame') and
                t.get('structure_occupancy_source') == survey['structure_source_id'] and
                type(t.get('on_structure_verified')) is bool and
                isinstance(t.get('velocity_xyz_mps'), list)
                for i, (t, m) in enumerate(zip(trace, frames))), 'Original velocity/occupancy/frame join missing')
    require(any(t['on_structure_verified'] for t in trace), 'No sourced structure occupancy')
    result = json.loads((attempt / 'result.json').read_text())
    finding = json.loads((attempt / 'bridge-findings.json').read_text())
    require(result.get('case_id') == case and result.get('physical_checks') and finding.get('case_id') == case,
            'Selected source analysis incomplete or wrong case')
    require(finding.get('original_bridge_survey_sha256') == sha(attempt / 'original_bridge_survey.json') and
            finding.get('original_native_trace_sha256') == sha(attempt / 'bridge-native.jsonl') and
            finding.get('original_frame_map_sha256') == sha(attempt / 'video_frames.jsonl'),
            'Saved finding changed original source')
    require(finding.get('legal_result') is None and finding.get('physical_completion') is False,
            'Premature legal or physical acceptance')
    map_hash = sha(attempt / 'video_frames.jsonl')
    for i, name in enumerate(('overview', 'approach', 'reference_corner', 'driver_reference', 'raw')):
        media = attempt / (name + '.mkv')
        receipt = attempt / ('source-' + str(i) + '.json')
        require(media.is_file() and receipt.is_file(), 'Missing decoded original video: ' + name)
        decoded = json.loads(receipt.read_text())
        require(decoded.get('passed') is True and decoded.get('frames') == 600 and
                decoded.get('video_sha256') == sha(media) and decoded.get('mapping_sha256') == map_hash and
                decoded.get('rgb_sequence_sha256'), 'Original video pixels/frame decode missing: ' + name)
    final = json.loads((attempt / 'final-decode.json').read_text())
    require(final.get('passed') is True and final.get('frames') == 600 and
            final.get('video_sha256') == sha(attempt / 'event_review.webm') and
            final.get('rgb_sequence_sha256'), 'Final review pixels not decoded')
    require(provenance.get('provenance_kind') == 'synthetic_fixture' and provenance.get('diagnostic_fixture') is True,
            'CPU proof needs explicit synthetic provenance; original delivery remains pending')
    return {'case_id': case, 'original_frames': 600, 'camera_sources': 4,
            'recorded_speed_separate_from_requested': True, 'source_gated_authority': True,
            'synthetic_cpu_diagnostic_only': True, 'original_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt), sort_keys=True))
