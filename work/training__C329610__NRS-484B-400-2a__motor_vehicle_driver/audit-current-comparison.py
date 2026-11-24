"""Audit current-runtime saved measurements against exact synthetic source pair."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    cases = manifest['cases']
    assert len(cases) == 2
    sources = [HERE / 'current-fixture' / c['case_id'].rsplit('__', 1)[-1] for c in cases]
    reports = []
    rows = []
    for case, source in zip(cases, sources):
        suffix = case['case_id'].rsplit('__', 1)[-1]
        processing = json.loads((HERE / 'current-public' / (suffix + '-primary-processing.json')).read_text())
        path = Path(processing['analysis_directory']) / 'analysis-report.json'
        report = json.loads(path.read_text())
        if (report['case_id'] != case['case_id'] or report['candidate_id'] != 'primary'
                or report['effective_provenance_kind'] != 'synthetic_fixture'
                or report['original_joins']['frames'] != 480
                or not all(value == 480 for value in report['video_frames'].values())
                or not processing['passed'] or not processing['recorded_only']
                or not processing['originals_preserved'] or processing['physical_acceptance_claimed']):
            raise ValueError('Saved comparison source not bound to selected diagnostic')
        reports.append(report)
        rows.append(lines(source / 'native_samples.jsonl'))
    if (sources[0] / 'road_geometry.json').read_bytes() != (sources[1] / 'road_geometry.json').read_bytes():
        raise ValueError('Road geometry differs')
    if len(rows[0]) != len(rows[1]) or len(rows[0]) != 480:
        raise ValueError('Source lengths differ')
    for index, (first, second) in enumerate(zip(*rows)):
        for key in ('native_frame', 'time_s', 'native_forward_xy'):
            if first[key] != second[key]:
                raise ValueError('Comparison changed ' + key)
        if not math.isclose(first['native_center_xy_m'][0], second['native_center_xy_m'][0], abs_tol=1e-9):
            raise ValueError('Comparison changed longitudinal motion')
        expected = 3.5 if index < 160 else 3.5 * (1 - (index - 160) / 159) if index < 320 else 0
        if not math.isclose(second['native_center_xy_m'][1] - first['native_center_xy_m'][1], expected, abs_tol=1e-9):
            raise ValueError('Unexpected lateral comparison difference')
    offsets = [r['measurements']['approach_placement_geometry']['value']['sampled_right_offset_m']['mean'] for r in reports]
    if offsets != [1.75, 5.25]:
        raise ValueError('Saved approach measurements changed')
    if not all(r['measurements']['approach_placement_geometry']['value']['full_body_right_half'] for r in reports):
        raise ValueError('Right-half source geometry changed')
    return {'format': 'c329610-current-saved-comparison', 'case_ids': [c['case_id'] for c in cases],
            'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
            'frames_per_case': 480, 'road_geometry_sha256': sha(sources[0] / 'road_geometry.json'),
            'native_sample_sha256': [sha(s / 'native_samples.jsonl') for s in sources],
            'saved_mean_right_offset_m': offsets, 'only_deliberate_difference': 'approach lateral offset',
            'full_body_within_right_half': True, 'diagnostic_only': True,
            'original_native_observed': False, 'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
