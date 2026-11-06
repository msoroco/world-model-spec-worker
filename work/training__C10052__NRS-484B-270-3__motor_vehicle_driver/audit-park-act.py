"""Independent raw-source audit of the synthetic parking-control pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def clipped_area(points, bounds):
    x1, y1, x2, y2 = bounds
    polygon = [tuple(point) for point in points]
    for axis, edge, greater in ((0, x1, True), (0, x2, False),
                                (1, y1, True), (1, y2, False)):
        result = []
        for before, after in zip(polygon[-1:] + polygon[:-1], polygon):
            before_inside = before[axis] >= edge if greater else before[axis] <= edge
            after_inside = after[axis] >= edge if greater else after[axis] <= edge
            if before_inside != after_inside:
                ratio = (edge - before[axis]) / (after[axis] - before[axis])
                result.append(tuple(before[j] + ratio * (after[j] - before[j]) for j in range(2)))
            if after_inside:
                result.append(after)
        polygon = result
        if not polygon:
            return 0.0
    return abs(sum(a[0]*b[1] - a[1]*b[0]
                   for a, b in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def main():
    summary = json.loads((HERE / 'park-act-summary.json').read_text())
    assert summary['format'] == 'c10052-park-act-synthetic-proof-v1'
    base = ROOT / summary['fixture_root']
    observations = {}
    for variant in ('stationary_stop', 'short_handbrake', 'parking_control'):
        folder = base / variant
        report = summary['variants'][variant]
        manifest = json.loads((folder / 'park-act-sources.json').read_text())
        assert manifest['source_kind'] == report['source_kind'] == 'synthetic_cpu_fixture'
        for name, digest in manifest['sha256'].items():
            assert sha(folder / name) == digest == report['source_sha256'][name]
        poses, controls = rows(folder / 'native_samples.jsonl'), rows(folder / 'native_controls.jsonl')
        geometry = json.loads((folder / 'road_geometry.json').read_text())
        assert len(poses) == len(controls) == report['original_frame_count'] == 480
        bounds = geometry['bicycle_facility_native_xy_bounds_m']
        active = []
        areas = []
        for pose, control in zip(poses, controls):
            assert pose['native_frame'] == control['native_frame']
            assert pose['time_s'] == control['time_s']
            assert pose['synthetic_diagnostic'] is control['synthetic_diagnostic'] is True
            area = clipped_area(pose['native_body_xy_m'], bounds)
            areas.append(area)
            active.append(pose['speed_mps'] <= .1 and control['throttle'] <= .01 and control['hand_brake'] and area > .01)
        runs = []
        start = None
        for i, flag in enumerate(active + [False]):
            if flag and start is None:
                start = i
            if not flag and start is not None:
                if i-start >= 40:
                    runs.append((start, i))
                start = None
        longest = max(runs, key=lambda item: item[1]-item[0], default=None)
        assert report['park_control_candidate'] == (longest is not None)
        assert report['first_held_native_frame'] == (None if longest is None else poses[longest[0]]['native_frame'])
        assert report['held_duration_s'] == (0 if longest is None else (longest[1]-longest[0])/20)
        assert report['max_held_facility_overlap_m2'] == (0 if longest is None else round(max(areas[longest[0]:longest[1]]), 6))
        assert report['facility_designation_verified'] is False
        assert report['statutory_exceptions_verified'] is False
        assert report['legal_park_verdict_claimed'] is False and report['accepted'] is False
        observations[variant] = {'run': longest, 'max_area_m2': max(areas)}
    stop, park = (base / name for name in ('stationary_stop', 'parking_control'))
    assert (stop / 'native_samples.jsonl').read_bytes() == (park / 'native_samples.jsonl').read_bytes()
    assert (stop / 'road_geometry.json').read_bytes() == (park / 'road_geometry.json').read_bytes()
    assert summary['negatives'] == ['synthetic_as_original', 'changed_control_hash', 'control_pose_join']
    assert observations['stationary_stop']['run'] is None
    assert observations['short_handbrake']['run'] is None
    assert observations['parking_control']['run'] is not None
    print(json.dumps({'audit': 'passed', 'held_run': observations['parking_control']['run'],
                      'same_pose_and_geometry': True, 'selected': False}, sort_keys=True))


if __name__ == '__main__':
    main()
