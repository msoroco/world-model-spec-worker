"""Independently check the 3(a) diagnostic pair against exact package outputs."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
CASES=('controlled_1','controlled_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
MAP_SHA='26d501449afedc978633694391bcd716ea4f674dcdedd3503011f5685ed6e78e'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(path.read_text())


def audit():
    manifest=read(FOLDER/'draft-execution-manifest.json')
    policies=read(FOLDER/'draft-construction/candidate-manifest.json')
    entries={row['case_id']:row for row in manifest['cases']}
    fixed=None;rows=[]
    for case in CASES:
        case_id=FOLDER.name+'__'+case
        entry=entries[case_id]
        refs={'primary':entry,**{r['id']:r for r in entry['candidates']}}
        assert set(refs)==set(CANDIDATES)
        for candidate in CANDIDATES:
            receipt_log=FOLDER/f'probe-package-{case}-{candidate}.log'
            log_lines=receipt_log.read_text().splitlines()
            assert len(log_lines)==2 and log_lines[0].startswith('scratch ')
            source=Path(log_lines[0].removeprefix('scratch '))/'output'
            assert source.is_dir() and source.is_relative_to(FOLDER.parents[1]/'.runtime-work')
            config=read(source/'config.json');report=read(source/'analysis-report.json')
            result=read(source/'result.json');compat=read(source/'compatibility.json')
            assert config['case_id']==case_id and config['candidate_id']==candidate
            assert result['case_id']==case_id and compat['case_id']==case_id
            assert compat['construction_sha256']==refs[candidate]['construction_sha256']
            assert compat['passed'] is True and compat['format']=='worker-package-compatibility-v1'
            assert report['original_joins']['frames']==480
            assert set(report['video_frames'].values())=={480}
            measured=report['measurements']['center_turn_purpose_and_movement']
            assert measured['method']=='purpose_movement'
            assert measured['sources']['scene.xodr']==MAP_SHA
            assert measured['sources']['native_samples.jsonl']==sha(source/'native_samples.jsonl')
            assert measured['sources']['road_geometry.json']==sha(source/'road_geometry.json')
            assert measured['sources']['declared_purpose.json']==sha(source/'declared_purpose.json')
            value=measured['value'];movement=value['movement']
            assert value['requested_movement_observed_in_saved_rows'] is True
            assert value['declared_purpose_is_observed_driver_intent'] is False
            assert value['legal_verdict'] is None
            assert result['setup_confirmed'] is False and result['behavior_attempted'] is False
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            assert result['provenance_kind']=='synthetic_local_diagnostic'
            assert config['cell_id']=='C394300' and config['actor']=='motor_vehicle_driver'
            assert config['duration_s']==24 and config['rate_hz']==20
            current_fixed=(config['cell_id'],config['actor'],config['law_id'],
                config['duration_s'],config['rate_hz'],config['required_atoms'],
                config['mandatory_channels'],config['recording_description'],config['cameras'])
            if fixed is None:fixed=current_fixed
            assert current_fixed==fixed
            if case=='controlled_1':
                assert movement['first_left_connector_frames']>0
                assert movement['first_left_exit_frames']>0
                assert movement['later_left_connector_frames']==0
                assert movement['later_left_exit_frames']==0
                assert value['declared_purpose']=='left_turn_from_center_at_first_opportunity'
            else:
                assert movement['first_opportunity_center_through_frames']>0
                assert movement['later_through_full_body_frames']>0
                assert movement['later_left_connector_frames']>0
                assert movement['later_left_exit_frames']>0
                assert movement['first_left_connector_frames']==0
                assert value['declared_purpose']=='through_travel_then_later_left_from_through_lane'
            if candidate!='primary':
                policy=next(p for p in policies['cases'] if p['case_id']==case_id and p['candidate_id']==candidate)
                assert refs[candidate]['trigger']==policy['trigger']
                assert refs[candidate]['changed_knobs']
            rows.append({'case_id':case_id,'candidate_id':candidate,
                'construction_sha256':compat['construction_sha256'],
                'source_map_sha256':MAP_SHA,
                'center_full_body_frames':movement['center_full_body_frames'],
                'first_opportunity_center_through_frames':movement['first_opportunity_center_through_frames'],
                'first_left_connector_frames':movement['first_left_connector_frames'],
                'later_left_connector_frames':movement['later_left_connector_frames'],
                'analysis_report_sha256':sha(source/'analysis-report.json'),
                'compatibility_receipt_sha256':sha(source/'compatibility.json'),
                'log_sha256':sha(receipt_log)})
    assert len(rows)==8
    return {'format':'c394300-3a-diagnostic-controlled-comparison-v1','passed':True,
        'cases':2,'candidate_packages':8,'common_fixed_conditions_verified':True,
        'lawful_purpose_or_physical_acceptance_inferred':False,'results':rows}


if __name__=='__main__':print(json.dumps(audit(),indent=2))
