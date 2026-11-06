"""Independent raw-source audit of the saved parking-control integration."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('park_audit', HERE/'audit-park-act.py')
park_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(park_audit)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary = json.loads((HERE/'park-saved-integration-summary.json').read_text())
    assert summary['format'] == 'c10052-park-saved-integration-v1'
    assert summary['selected'] is False and summary['positive_result_accepted'] is False
    base = ROOT/'.runtime-work'/'c10052-park-saved-integration'/'audit-sources'
    positive, negative = base/'positive', base/'negative'
    manifest = json.loads((positive/'park-act-sources.json').read_text())
    report = json.loads((positive/'analysis-report.json').read_text())
    result = json.loads((positive/'result.json').read_text())
    observation = report['measurements']['parking_control_observation']
    assert observation == summary['positive_measurement']
    assert manifest['source_kind'] == summary['source_kind'] == 'synthetic_cpu_fixture'
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    assert summary['original_hashes_unchanged'] is True
    for name, digest in manifest['sha256'].items():
        assert sha(positive/name) == digest == observation['sources'][name]
    poses = park_audit.rows(positive/'native_samples.jsonl')
    controls = park_audit.rows(positive/'native_controls.jsonl')
    geometry = json.loads((positive/'road_geometry.json').read_text())
    assert len(poses) == len(controls) == 480
    bounds = geometry['bicycle_facility_native_xy_bounds_m']
    active, areas = [], []
    for pose, control in zip(poses, controls):
        assert pose['native_frame'] == control['native_frame']
        assert pose['time_s'] == control['time_s']
        assert control['control_source'] == 'synthetic_fixture'
        area = park_audit.clipped_area(pose['native_body_xy_m'], bounds)
        areas.append(area)
        active.append(pose['speed_mps'] <= .1 and control['throttle'] <= .01 and
                      control['hand_brake'] and area > .01)
    held = [i for i, flag in enumerate(active) if flag]
    assert held == list(range(160,440))
    value = observation['value']
    assert value['park_control_candidate'] is True
    assert value['first_held_native_frame'] == poses[160]['native_frame']
    assert value['held_duration_s'] == len(held)/20 == 14.0
    assert value['max_held_facility_overlap_m2'] == round(max(areas[i] for i in held),6) == 9.36
    assert value['facility_designation_verified'] is False
    assert value['statutory_exceptions_verified'] is False
    assert value['legal_park_verdict_claimed'] is False
    assert (positive/'native_samples.jsonl').read_bytes() == (negative/'native_samples.jsonl').read_bytes()
    assert (positive/'road_geometry.json').read_bytes() == (negative/'road_geometry.json').read_bytes()
    assert (positive/'park-act-sources.json').read_bytes() == (negative/'park-act-sources.json').read_bytes()
    assert sha(negative/'native_controls.jsonl') != manifest['sha256']['native_controls.jsonl']
    assert summary['negative'] == 'changed_control_hash_rejected'
    print(json.dumps({'audit':'passed','held_frames':len(held),'max_overlap_m2':9.36,
                      'negative_control_hash_changed':True,'selected':False},sort_keys=True))


if __name__ == '__main__':
    main()
