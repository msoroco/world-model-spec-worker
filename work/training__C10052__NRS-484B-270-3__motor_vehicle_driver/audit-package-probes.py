"""Independently inspect all diagnostic exact package positive/negative executions."""
import hashlib
import json
from pathlib import Path
import sys
from audit_geometry import clipped_area, footprint_gap

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.common import digest,tree
SUFFIXES=('probe_a','probe_b')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    rows=[]
    for suffix in SUFFIXES:
        entry=next(row for row in manifest['cases'] if row['case_id'].endswith('__'+suffix))
        for candidate in CANDIDATES:
            filename='package-compatibility-'+suffix+('' if candidate=='primary' else '-'+candidate)+'.log'
            log=HERE/filename
            lines=log.read_text().splitlines()
            if len(lines)!=2 or not lines[0].startswith('scratch '):
                raise ValueError('Incomplete diagnostic run: '+filename)
            scratch=Path(lines[0][8:])
            if ROOT/'.runtime-work' not in scratch.parents:
                raise ValueError('Unexpected scratch location')
            result=json.loads(lines[1]);positive=result['positive'];negative=result['negative']
            if result.get('case_suffix')!=suffix or result.get('candidate')!=candidate:
                raise ValueError('Wrong diagnostic identity')
            selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            if (positive['format']!='worker-package-compatibility-v1' or positive['passed'] is not True
                or positive['case_id']!=entry['case_id'] or positive['candidate_id']!=candidate
                or positive['construction_sha256']!=selected['construction_sha256']
                or positive['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256']):
                raise ValueError('Stale or failed positive '+suffix+' '+candidate)
            required={'actual_analysis','native_validation','mandatory_observations','lean_decoder',
                      'render','final_decode','acquisition_unchanged'}
            if not required<=set(positive['checks']):
                raise ValueError('Missing positive check')
            stored=json.loads((scratch/'output/compatibility.json').read_text())
            if any(stored.get(key)!=value for key,value in positive.items()):
                raise ValueError('Saved receipt differs from log')
            if digest(tree(scratch/'fixture'))!=positive['fixture_sha256']:
                raise ValueError('Diagnostic fixture changed')
            if sha(scratch/'output/finalize.py')!=positive['analysis_sha256']:
                raise ValueError('Packaged finalizer changed')
            if sha(scratch/'output/compatibility-analysis.log')!=positive['log_sha256']:
                raise ValueError('Saved analysis log changed')
            if not all(json.loads((scratch/'output'/f'source-{i}.json').read_text())['passed']
                       and json.loads((scratch/'output'/f'source-{i}.json').read_text())['frames']==480
                       for i in range(4)):
                raise ValueError('Missing source-video audit')
            if not json.loads((scratch/'output/final-decode.json').read_text())['passed']:
                raise ValueError('Final render decode failed')
            native_result=json.loads((scratch/'output/result.json').read_text())
            if native_result['accepted'] or native_result['legal_verdict_claimed'] or any(
                check.get('physical_cause_confirmed') for check in native_result['target_checks']):
                raise ValueError('Synthetic diagnostic claimed physical success or acceptance')
            measured=json.loads((scratch/'output/analysis-report.json').read_text())
            if (measured['measurements']['facility_stop_observation']['value']['observed_exception_status']
                != 'unresolved'):
                raise ValueError('Synthetic exception request promoted to observation')
            entry_measure=measured['measurements']['moving_entry_observation']
            source=json.loads((scratch/'output/entry-sources.json').read_text())
            if source['source_kind']!='synthetic_cpu_fixture':
                raise ValueError('Synthetic entry source provenance changed')
            if entry_measure['sources']!=source['sha256']:
                raise ValueError('Moving entry source hashes differ')
            for name,expected_hash in source['sha256'].items():
                if sha(scratch/'output'/name)!=expected_hash:
                    raise ValueError('Moving entry source bytes differ')
            raw=[json.loads(line) for line in (scratch/'output/native_samples.jsonl').read_text().splitlines()]
            if len(raw)!=480:raise ValueError('Moving entry source duration differs')
            facility=json.loads((scratch/'output/road_geometry.json').read_text())[
                'bicycle_facility_native_xy_bounds_m']
            alley=json.loads((scratch/'output/road_geometry.json').read_text())[
                'alley_entrance_native_xy_bounds_m']
            areas=[clipped_area(sample['native_body_xy_m'],facility) for sample in raw]
            park_source=json.loads((scratch/'output/park-act-sources.json').read_text())
            if park_source['source_kind']!='synthetic_cpu_fixture' or set(park_source['sha256'])!={
                    'native_samples.jsonl','native_controls.jsonl','road_geometry.json'}:
                raise ValueError('Parking source manifest differs')
            for name,expected_hash in park_source['sha256'].items():
                if sha(scratch/'output'/name)!=expected_hash:
                    raise ValueError('Parking source bytes differ')
            controls=[json.loads(line) for line in (scratch/'output/native_controls.jsonl').read_text().splitlines()]
            if len(controls)!=480:
                raise ValueError('Parking control count differs')
            held=[]
            for i,(pose,control,area) in enumerate(zip(raw,controls,areas)):
                if (pose['native_frame']!=control['native_frame'] or
                    pose['time_s']!=control['time_s'] or
                    control['control_source']!='synthetic_fixture'):
                    raise ValueError('Parking control source join differs')
                if (pose['speed_mps']<=.1 and control['throttle']<=.01 and
                    control['hand_brake'] and area>.01):
                    held.append(i)
            park_measure=measured['measurements']['parking_control_observation']
            park_value=park_measure['value']
            if (park_measure['sources']!=park_source['sha256'] or
                held!=(list(range(160,440)) if suffix=='probe_b' else []) or
                park_value['park_control_candidate']!=(suffix=='probe_b') or
                park_value['held_duration_s']!=(14.0 if suffix=='probe_b' else 0) or
                park_value['first_held_native_frame']!=(raw[160]['native_frame'] if suffix=='probe_b' else None) or
                park_value['max_held_facility_overlap_m2']!=(9.36 if suffix=='probe_b' else 0) or
                park_value['facility_designation_verified'] is not False or
                park_value['statutory_exceptions_verified'] is not False or
                park_value['legal_park_verdict_claimed'] is not False):
                raise ValueError('Parking-control saved measurement differs')
            gaps=[footprint_gap(sample['native_body_xy_m'],alley) for sample in raw]
            moving=[sample['speed_mps']>.1 for sample in raw]
            first=next((i for i in range(1,480)
                        if areas[i-1]<=.01 and areas[i]>.01 and moving[i]),None)
            value=entry_measure['value']
            occupied_gaps=[gap for flag,area,gap in zip(moving,areas,gaps)
                           if flag and area>.01]
            if (value['moving_entry_measured']!=(first is not None) or
                value['first_moving_entry_native_frame']!=(
                    None if first is None else raw[first]['native_frame']) or
                value['moving_occupied_frames']!=sum(flag and area>.01
                    for flag,area in zip(moving,areas)) or
                value['first_entry_alley_footprint_gap_m']!=
                    (None if first is None else round(gaps[first],6)) or
                value['minimum_moving_facility_alley_footprint_gap_m']!=
                    (None if not occupied_gaps else round(min(occupied_gaps),6)) or
                value['moving_facility_alley_footprint_overlap_frames']!=
                    sum(gap<=1e-6 for gap in occupied_gaps) or
                value['facility_designation_verified'] is not False or
                value['exception_a_observed']!='unresolved'):
                raise ValueError('Moving entry saved measurement differs')
            if (value['moving_entry_measured']!=(suffix=='probe_b') or
                value['moving_occupied_frames']!=(71 if suffix=='probe_b' else 0)):
                raise ValueError('Moving entry controlled pair differs')
            if (value['moving_facility_alley_footprint_overlap_frames']!=0 or
                (suffix=='probe_b' and (value['first_entry_alley_footprint_gap_m']<=20 or
                 value['minimum_moving_facility_alley_footprint_gap_m']<=6))):
                raise ValueError('Alley footprint controlled comparison differs')
            if (negative['exit_code']==0 or negative['removed']!='exception_context.json'
                or negative['error_contains']!='Missing required source: exception_context.json'
                or negative['error_contains'] not in (scratch/'negative-analysis.log').read_text()):
                raise ValueError('Negative proof absent')
            entry_negative=result['entry_negative']
            if (entry_negative['exit_code']==0 or
                entry_negative['removed']!='entry-sources.json' or
                entry_negative['error_contains'] not in
                    (scratch/'entry-negative-analysis.log').read_text()):
                raise ValueError('Entry-source negative proof absent')
            park_negative=result['park_negative']
            if (park_negative['exit_code']==0 or
                park_negative['changed']!='native_controls.jsonl' or
                park_negative['error_contains']!='Parking source hash differs: native_controls.jsonl' or
                park_negative['error_contains'] not in
                    (scratch/'park-negative-analysis.log').read_text() or
                (scratch/'park-negative/result.json').exists()):
                raise ValueError('Parking-source negative proof absent')
            rows.append({'case_suffix':suffix,'candidate':candidate,
                         'positive_receipt_sha256':sha(scratch/'output/compatibility.json'),
                         'negative_log_sha256':sha(scratch/'negative-analysis.log'),
                         'entry_negative_log_sha256':sha(scratch/'entry-negative-analysis.log'),
                         'park_negative_log_sha256':sha(scratch/'park-negative-analysis.log'),
                         'command_log_sha256':sha(log),'scope':'synthetic diagnostic v1, unselected'})
    output={'format':'c10052-270-3-diagnostic-package-audit-v1','count':len(rows),'rows':rows,
            'ready':False,'strict_v2_compatibility':False}
    (HERE/'draft-package-probe-summary.json').write_text(json.dumps(output,indent=2)+'\n')
    return output


if __name__=='__main__':print(json.dumps(audit(),indent=2))
