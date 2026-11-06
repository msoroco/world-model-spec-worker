"""Independent exact-source/receipt audit of C104538's 12 unselected v1 probes."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    root = REPO / '.runtime-work/c104538/joined-package-matrix-v6'
    summary = read(HERE / 'joined-package-matrix-summary.json')
    manifest = read(HERE / 'draft-execution-manifest.json')
    expected = {case['case_id']: case for case in manifest['cases']}
    assert summary['selected'] is False and summary['accepted'] is False
    assert len(summary['cases']) == len(expected) == 3
    ids = set()
    construction_hashes = set()
    road_hashes = set()
    obstruction_hashes = set()
    measured_reference_limits = {}
    for case in summary['cases']:
        case_id, suffix = case['case_id'], case['suffix']
        assert case_id in expected and case_id.endswith('__'+suffix)
        assert len(case['candidates']) == 4
        road = HERE / 'draft-sightline' / suffix / 'road.xodr'
        road_hashes.add(sha(road))
        source_motion_signatures = set()
        for row in case['candidates']:
            candidate = row['candidate_id']
            assert candidate in ('primary','fallback1','fallback2','fallback3')
            assert (case_id,candidate) not in ids
            ids.add((case_id,candidate))
            fixture = root / suffix / (candidate+'-fixture')
            output = root / suffix / candidate
            assert row['fixture_trace_sha256'] == sha(fixture / 'trace.jsonl')
            assert row['fixture_road_sha256'] == sha(road) == sha(fixture / 'road.xodr')
            obstruction = read(fixture / 'authored-obstruction-source.json')
            assert obstruction['case_suffix'] == suffix
            assert obstruction['road_xodr_sha256'] == sha(road)
            assert obstruction['native_actor_spawned'] is False
            assert obstruction['physical_opacity_measured'] is False
            obstruction_hashes.add(sha(fixture / 'authored-obstruction-source.json'))
            capture_manifest = read(fixture / 'capture/manifest.json')
            assert capture_manifest['sources']['authored-obstruction-source.json'] == sha(
                fixture / 'authored-obstruction-source.json')
            measured_ft = 1000 * math.acos(obstruction['inner_radius_m']/500) / 0.3048
            assert math.isclose(measured_ft, obstruction['requested_reference_limit_ft'], abs_tol=1e-8)
            measured_reference_limits[suffix] = measured_ft
            context = read(fixture / 'native-construction-context.json')
            assert context['case_id'] == case_id and context['candidate_id'] == candidate
            assert context['authored_obstruction_sha256'] == sha(fixture / 'authored-obstruction-source.json')
            assert context['authored_road_sha256'] == sha(fixture / 'road.xodr')
            assert context['synthetic_coordinate_alignment']['physical_native_observation'] is False
            trace = rows(fixture / 'trace.jsonl')
            assert len(trace) == 480
            source_motion_signatures.add(hashlib.sha256(json.dumps([
                [t['frame'],t['time_s'],t['position_m'],t['velocity_mps'],t['heading_deg']]
                for t in trace],sort_keys=True).encode()).hexdigest())
            calibration = read(fixture / 'environment_calibration.json')
            surface = read(fixture / 'surface_provenance.json')
            assert calibration['source_kind'] == surface['source_kind'] == 'synthetic_cpu_fixture'
            assert calibration['original_native_pixels'] is False
            for sample in calibration['samples']:
                for key in ('rgb','instance'):
                    assert sha(fixture / sample[key]['path']) == sample[key]['sha256']
            for t in trace:
                env = t['environment_measurements']
                assert env['frame'] == t['frame'] and env['time_s'] == t['time_s']
                assert env['calibration_sha256'] == sha(fixture / 'environment_calibration.json')
                assert env['surface_sha256'] == sha(fixture / 'surface_provenance.json')
            receipt = read(output / 'compatibility.json')
            assert receipt == row['positive'] and receipt['passed'] is True
            assert receipt['case_id'] == case_id and receipt['candidate_id'] == candidate
            assert row['positive_receipt_sha256'] == sha(output / 'compatibility.json')
            assert {'actual_analysis','native_validation','mandatory_observations',
                    'lean_decoder','render','final_decode','acquisition_unchanged'} <= set(receipt['checks'])
            selected = (expected[case_id] if candidate == 'primary' else next(
                c for c in expected[case_id]['candidates'] if c['id'] == candidate))
            assert receipt['construction_sha256'] == selected['construction_sha256']
            construction_hashes.add(receipt['construction_sha256'])
            assert read(output / 'converted/adapter_report.json')['atom_coverage']['passed'] is True
            assert (output / 'final-decode.json').is_file()
            assert read(output / 'result.json')['accepted'] is False
            measured = read(output / 'result.json')['measured_values']
            assert math.isclose(measured['authored_center_reference_limit_ft'], measured_ft, abs_tol=1e-8)
            assert measured['authored_obstruction_source_sha256'] == sha(output / 'obstruction.json')
            assert measured['source_sha256']['obstruction.json'] == sha(output / 'obstruction.json')
            assert measured['authored_road_source_sha256'] == sha(output / 'authored_road.xodr')
            assert measured['source_sha256']['authored_road.xodr'] == sha(output / 'authored_road.xodr')
            negative_log = root / suffix / (candidate+'-negative.log')
            assert row['negative_exit_code'] != 0
            assert row['negative_removed'] == 'native_body_history.jsonl'
            assert row['negative_log_sha256'] == sha(negative_log)
            assert 'native_body_history.jsonl' in negative_log.read_text()
            changed_log = root / suffix / (candidate+'-changed-obstruction.log')
            assert row['changed_obstruction_exit_code'] != 0
            assert row['changed_obstruction_log_sha256'] == sha(changed_log)
            assert 'Authored obstruction source hash differs' in changed_log.read_text()
            road_log = root / suffix / (candidate+'-changed-road.log')
            assert row['changed_road_exit_code'] != 0
            assert row['changed_road_log_sha256'] == sha(road_log)
            assert 'Authored road source hash differs' in road_log.read_text()
            changed_road = root / suffix / (candidate+'-changed-road')
            assert sha(changed_road / 'authored_road.xodr') != sha(output / 'authored_road.xodr')
            assert read(changed_road / 'native-construction-context.json')['authored_road_sha256'] == sha(
                output / 'authored_road.xodr')
        assert len(source_motion_signatures) == 1
    assert len(ids) == len(construction_hashes) == 12
    # The comparison changes an authored obstruction radius, not OpenDRIVE.
    assert len(road_hashes) == 1
    assert len(obstruction_hashes) == 3
    assert all(math.isclose(measured_reference_limits[suffix],target,abs_tol=1e-8)
               for suffix,target in [('below_500_ft',450),('at_500_ft',500),('above_500_ft',550)])
    print(json.dumps({'passed': True,'cases': 3,'candidates': 12,
        'positive_receipts': 12,'removed_source_negatives': 12,
        'changed_obstruction_negatives': 12,
        'changed_road_negatives': 12,
        'distinct_construction_hashes': len(construction_hashes),
        'distinct_case_roads': len(road_hashes),
        'distinct_authored_obstructions': len(obstruction_hashes),
        'authored_center_reference_sweep_ft': measured_reference_limits,
        'physical_controlled_comparison_proven': False,
        'summary_sha256': sha(HERE / 'joined-package-matrix-summary.json'),
        'scope': 'exact unselected synthetic v1 software compatibility only'},sort_keys=True))


if __name__ == '__main__':
    main()
