"""Independent C10052 full saved synthetic receipt and controlled-pair audit."""
import hashlib
import json
from pathlib import Path
from audit_geometry import clipped_area, footprint_gap

HERE = Path(__file__).resolve().parent
OUTPUT = HERE/'draft-facility'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit():
    summary = json.loads((HERE/'saved-diagnostic-summary.json').read_text())
    assert summary['ready'] is False and len(summary['rows']) == 2
    source_rows = {}
    for entry in summary['rows']:
        suffix, folder = entry['suffix'], OUTPUT/entry['suffix']
        report = json.loads((folder/'saved-analysis-report.json').read_text())
        result = json.loads((folder/'saved-result.json').read_text())
        contract = json.loads((folder/'measurement-contract.json').read_text())
        samples = rows(folder/'native_samples.jsonl')
        source_rows[suffix] = samples
        assert len(samples) == 480
        assert sha(folder/'saved-analysis-report.json') == entry['positive_report_sha256']
        assert sha(folder/'saved-result.json') == entry['result_sha256']
        assert entry['source_hashes']['native_samples.jsonl'] == sha(folder/'native_samples.jsonl')
        assert entry['source_hashes']['road_geometry.json'] == sha(folder/'road_geometry.json')
        context = json.loads((folder/'exception_context.json').read_text())
        context['requested_exception_context'] = {key: context[key] for key in
            ('source_kind', 'exceptions', 'note')}
        context_hash = hashlib.sha256(json.dumps(context).encode()).hexdigest()
        assert entry['source_hashes']['exception_context.json'] == context_hash
        assert report['original_joins']['frames'] == 480
        assert set(report['video_frames'].values()) == {480}
        assert set(entry['source_videos'].values()) == {480}
        assert not result['accepted'] and not result['legal_verdict_claimed']
        assert result['setup_confirmed'] is False
        assert all(check['matched'] and check['physical_cause_confirmed'] is False
                   for check in result['target_checks'])
        assert contract['case_id'] == result['case_id']
        assert {r['output_key'] for r in contract['requirements']} <= set(report['measurements'])
        measured = report['measurements']['facility_stop_observation']
        assert measured['sources'] == {name: entry['source_hashes'][name] for name in
            ('native_samples.jsonl', 'road_geometry.json', 'exception_context.json')}
        assert measured['value']['observed_exception_status'] == 'unresolved'
        assert measured['value']['yield_duty_measured'] is False
        entry_measure=report['measurements']['moving_entry_observation']
        assert entry_measure['sources']=={name:entry['source_hashes'][name] for name in
            ('native_samples.jsonl','road_geometry.json')}
        facility=json.loads((folder/'road_geometry.json').read_text())[
            'bicycle_facility_native_xy_bounds_m']
        alley=json.loads((folder/'road_geometry.json').read_text())[
            'alley_entrance_native_xy_bounds_m']
        areas=[]
        gaps=[]
        for sample in samples:
            areas.append(clipped_area(sample['native_body_xy_m'],facility))
            gaps.append(footprint_gap(sample['native_body_xy_m'],alley))
        moving=[sample['speed_mps']>.1 for sample in samples]
        first=next((i for i in range(1,480)
                    if areas[i-1]<=.01 and areas[i]>.01 and moving[i]),None)
        entry_value=entry_measure['value']
        assert entry_value['moving_entry_measured']==(first is not None)
        assert entry_value['first_moving_entry_native_frame']==(
            None if first is None else samples[first]['native_frame'])
        assert entry_value['moving_occupied_frames']==sum(
            flag and area>.01 for flag,area in zip(moving,areas))
        occupied_gaps=[gap for flag,area,gap in zip(moving,areas,gaps)
                       if flag and area>.01]
        assert entry_value['first_entry_alley_footprint_gap_m']==(
            None if first is None else round(gaps[first],6))
        assert entry_value['minimum_moving_facility_alley_footprint_gap_m']==(
            None if not occupied_gaps else round(min(occupied_gaps),6))
        assert entry_value['moving_facility_alley_footprint_overlap_frames']==sum(
            gap<=1e-6 for gap in occupied_gaps)
        assert entry_value['moving_facility_alley_footprint_overlap_frames']==0
        if suffix=='probe_b':
            assert entry_value['first_entry_alley_footprint_gap_m']>20
            assert entry_value['minimum_moving_facility_alley_footprint_gap_m']>6
        assert entry_value['facility_designation_verified'] is False
        assert entry_value['exception_a_observed']=='unresolved'
        assert result['measured_values']['moving_occupied_frames']==entry_value['moving_occupied_frames']
        assert 'Missing required source: exception_context.json' in (
            folder/'missing-source.log').read_text()
        assert entry['missing_source_exit_code'] != 0
        stop_y = -1.5 if suffix == 'probe_a' else -4.0
        stationary = [r for r in samples if r['speed_mps'] <= .1 and
                      r['native_road_id'] == 1]
        assert len(stationary) >= 40
        assert stationary[-1]['native_center_xy_m'] == [-12, stop_y]
        overlap = max(0, min(stop_y+.9, -3)-max(stop_y-.9, -5))*5.2
        assert result['measured_values']['max_stopped_overlap_m2'] == round(overlap, 6)
        assert measured['value']['max_stopped_overlap_m2'] == round(overlap, 6)
    for a, b in zip(source_rows['probe_a'][:61], source_rows['probe_b'][:61]):
        assert a == b
    result = {'format': 'c10052-independent-saved-pair-audit-v1',
              'cases': 2, 'shared_prefix_frames': 61,
              'outside_overlap_m2': 0.0, 'inside_overlap_m2': 9.36,
              'original_video_frames_per_view': 480,
              'observed_exception_status': 'unresolved',
              'physical_success_claimed': False, 'legal_verdict_claimed': False,
              'selected': False}
    (HERE/'saved-comparison-summary.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
