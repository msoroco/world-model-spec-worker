"""Independent draft primary compatibility/saved audit for all nine sweeps."""
import hashlib
import json
from pathlib import Path

from control_phase_measurement import measure_red_onset
from sweep_case import resolve

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSETS=ROOT/'.runtime-work/c179480-native-sweep'
REQUIRED_CHECKS={'acquisition_unchanged','actual_analysis','derived_outputs_rebuilt',
                 'final_decode','four_camera_sources','lean_decoder',
                 'mandatory_observations','native_validation','render',
                 'selected_measurements','negative_case_source'}
CAMERAS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=read(HERE/'sweep-primary-compatibility-manifest.json')
    if len(manifest['cases'])!=9:
        raise ValueError('Nine exact draft primaries required')
    rows=[]
    for item in manifest['cases']:
        cid=item['case_id'];attempt=ASSETS/'compatibility-final'/cid
        config=read(attempt/'config.json')
        base,axis,value=resolve(config)
        if (item['construction_sha256']!=sha(HERE/item['construction']) or
                item['case_id']!=config['case_id']):
            raise ValueError('Exact sweep construction changed: '+cid)
        compat=read(HERE/('sweep-final-'+cid+'-compatibility.log'))
        saved=read(HERE/('sweep-final-'+cid+'-saved.log'))
        if (not compat['passed'] or compat['case_id']!=cid or
                compat['construction_sha256']!=item['construction_sha256'] or
                compat['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256'] or
                not REQUIRED_CHECKS<=set(compat['checks'])):
            raise ValueError('Exact positive/negative compatibility proof missing: '+cid)
        negative=(attempt/'negative-analysis.log').read_text()
        if (compat['negative_removed']!='native-map-readback.json' or
                compat['negative_error_contains'] not in negative):
            raise ValueError('Missing-source negative did not reject: '+cid)
        if (not saved['passed'] or saved['case_id']!=cid or
                not saved['recorded_only'] or not saved['originals_preserved'] or
                saved['timestamp_joins']['frames']!=600 or
                not saved['timestamp_joins']['passed'] or saved['missing_evidence'] or
                saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
            raise ValueError('Recorded-only saved proof incomplete: '+cid)
        if any(not (attempt/name).is_file() for name in CAMERAS):
            raise ValueError('A required source camera is absent: '+cid)
        actors=[json.loads(line) for line in (attempt/'native-actors.jsonl').read_text().splitlines()]
        channel=[json.loads(line) for line in (attempt/'channels'/(axis+'.jsonl')).read_text().splitlines()]
        if len(actors)!=600 or len(channel)!=600:
            raise ValueError('Source-derived sweep channel lacks 600 joins: '+cid)
        if axis=='governing_red_onset_s':
            expected=measure_red_onset(attempt/'native-actors.jsonl',
                                        attempt/'video_frames.jsonl',
                                        expected_control_id=read(attempt/'native-map-readback.json')['surveyed_governing_traffic_light_id'],
                                        source_kind='synthetic_native_sample')['red_onset_s']
            values=[expected]*600
        elif axis=='following_gap_m':
            values=[row['following_gap_m'] for row in actors]
        else:
            values=[row['hazard_state']['ego_center_gap_m'] for row in actors]
        if [row['value'] for row in channel]!=values:
            raise ValueError('Sweep channel was not derived from retained actor source: '+cid)
        rows.append({'case_id':cid,'axis':axis,'point':value,
                     'compatibility_log_sha256':sha(HERE/('sweep-final-'+cid+'-compatibility.log')),
                     'saved_log_sha256':sha(HERE/('sweep-final-'+cid+'-saved.log')),
                     'actor_source_sha256':sha(attempt/'native-actors.jsonl')})
    return {'format':'c179480-independent-draft-sweep-primary-audit-v1',
            'passed':True,'manifest_sha256':sha(HERE/'sweep-primary-compatibility-manifest.json'),
            'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
            'case_count':9,'primary_compatibility_passed':9,
            'primary_recorded_only_saved_passed':9,'cases':rows,
            'selected_cases':0,'original_native_observed':False,
            'physical_or_legal_acceptance_claimed':False}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2,sort_keys=True))
