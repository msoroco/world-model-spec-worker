"""Selected CARLA execution entry point and saved-evidence validation."""
import json
import hashlib
import math
import subprocess
from pathlib import Path


def execute(store, run, python, host='127.0.0.1', port=20000, timeout=600, job_ids=()):
    from .engines import execute_pool
    return execute_pool(store, run, [{'id': 'single', 'python': python, 'host': host, 'port': port}],
                        timeout=timeout, job_ids=job_ids)


def verify_native_rgb_evidence(capture):
    manifest=json.loads((capture/'manifest.json').read_text())
    if manifest.get('observation_contract_version',0)<2:return
    for line in (capture/'evidence.jsonl').read_text().splitlines():
        packet=json.loads(line)['original_observations']
        if packet.get('world_settings',{}).get('no_rendering_mode')is not False or not packet.get('rgb_sensors'):
            raise ValueError('Original RGB recording requires a live native RGB sensor and enabled rendering in every frame')


def validate_attempt(directory, request, construction, metadata, dependency_hashes, *, source_audits=None):
    from .runtime_dependencies import assert_current
    result = json.loads((directory/'result.json').read_text())
    required = ('measured_values','target_checks','setup_confirmed','behavior_attempted','maneuver_completed',
                'termination_reason','physical_failure_flags','trace_reference','video_references','video_frame_map_reference',
                'recording_description','recording_evidence','realized_observables')
    if any(k not in result for k in required) or any(k in result for k in ('legal_verdict','compliant','violating')):
        raise ValueError('Missing execution evidence or prohibited compliance verdict')
    if construction.get('repair'):
        fixed={k:v for k,v in request['case']['variable_assignments'].items() if v.get('kind') in ('controller','world_setup')}
        if result.get('requested_variable_assignments')!=fixed:
            raise ValueError('Repaired execution changed or omitted approved setup/controller assignments')
        comparisons={c['target']:c for c in result['target_checks'] if isinstance(c.get('target'),str)}
        for prior in request.get('preserved_target_comparisons',[]):
            current=comparisons.get(prior['target'])
            if current is None or any(current.get(k)!=prior[k] for k in ('requested','tolerance')):
                raise ValueError('Repaired execution changed an approved target comparison or tolerance')
    if not result['target_checks']:
        raise ValueError('No measured target comparisons')
    for check in result['target_checks']:
        if any(k not in check for k in ('target','requested','measured','method','tolerance','matched','physical_cause_confirmed','cause_evidence')) or check['measured'] is None or not check['method']:
            raise ValueError('Incomplete target measurement')
        if isinstance(check['requested'],(float,int)) and isinstance(check['measured'],(float,int)):
            tolerance = check['tolerance']
            if isinstance(tolerance,(int,float)):
                if tolerance < 0 or not all(math.isfinite(v) for v in (tolerance, check['requested'], check['measured'])):
                    raise ValueError('Invalid target value/tolerance')
                if bool(check['matched']) != (abs(check['requested']-check['measured'])<=tolerance):
                    raise ValueError('Target comparison contradicts recorded measurement')
    def artifact_path(value):
        path = Path(value)
        path = path if path.is_absolute() else directory/path
        path = path.resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing or out-of-attempt recording: '+str(path))
        return path
    from .validation import recording_evidence
    recording_evidence(result, construction['recording_description'], artifact_path, request['case'].get('sweep_measurements', []))
    trace = [json.loads(line) for line in artifact_path(result['trace_reference']).read_text().splitlines()]
    mapping = [json.loads(line) for line in artifact_path(result['video_frame_map_reference']).read_text().splitlines()]
    for index, point in enumerate(trace):
        if any(k not in point for k in ('frame', 'time_s', 'position', 'heading_deg', 'speed_mps')):
            raise ValueError('Trace lacks position/heading/speed measurements')
        values = [point['time_s'], point['heading_deg'], point['speed_mps']] + [point['position'][k] for k in ('x', 'y', 'z')]
        if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values):
            raise ValueError('Nonfinite trace measurement')
        if index and (point['frame'] <= trace[index-1]['frame'] or point['time_s'] <= trace[index-1]['time_s']):
            raise ValueError('Trace frames/times must increase')
    if not trace or len(trace)!=len(mapping):
        raise ValueError('Incomplete frame mapping')
    if any(m.get('video_frame') != i for i, m in enumerate(mapping)):
        raise ValueError('Nonconsecutive video frame mapping')
    if any(t.get('frame')!=m.get('carla_frame') or abs(t.get('time_s',-1)-m.get('time_s',-2))>1e-6 for t,m in zip(trace,mapping)):
        raise ValueError('Video/trace frame mismatch')
    def file_digest(path):
        hasher = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    video_receipts=[]
    for value in result['video_references']:
        video = artifact_path(value)
        # Only the trusted local coordinator supplies these receipts. Never adopt
        # a runner's arbitrary claim. Pixel checks and frame counts can share a
        # prior complete source decode bound to this exact original frame map.
        supplied = (source_audits or {}).get(value)
        if supplied is not None:
            from worker_exchange.media import verify_receipt
            audit = verify_receipt(video, supplied, len(trace),
                                   mapping_sha256=file_digest(artifact_path(result['video_frame_map_reference'])))
            probe = {'streams': [{'nb_read_frames': audit['frames']}]}
            checksum = audit['video_sha256']
            verification = 'Reused exact-file complete source decode; checks retained in source_decode'
        else:
            probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                '-show_entries','stream=nb_read_frames','-of','json',str(video)],text=True))
            checksum = file_digest(video)
            verification = 'Generic executor full decoded-frame scan'
        if int(probe['streams'][0]['nb_read_frames']) != len(trace):
            raise ValueError('Video does not match trace length')
        receipt = {'reference': value, 'sha256': checksum, 'ffprobe': probe, 'verification': verification}
        if supplied is not None:
            receipt['source_decode'] = audit
        video_receipts.append(receipt)
    if not result['video_references']:
        raise ValueError('No usable camera footage')
    if (directory/'capture/manifest.json').exists():verify_native_rgb_evidence(directory/'capture')
    if 'runner_video_validation' not in result:
        result['runner_video_validation']=result.get('video_validation')
    result['video_validation']=video_receipts
    paths = [artifact_path(e['reference']) for e in result['recording_evidence']] + [artifact_path(result['trace_reference']), artifact_path(result['video_frame_map_reference'])] + [artifact_path(v) for v in result['video_references']]
    scanned_hashes={r['reference']:r['sha256'] for r in video_receipts}
    result['artifact_hashes'] = {str(p.relative_to(directory)): scanned_hashes.get(str(p.relative_to(directory))) or file_digest(p) for p in paths}
    result['rebuild_required'] = not bool(result['setup_confirmed'] and result['behavior_attempted'] and result['maneuver_completed'] and all(c['matched'] and c['physical_cause_confirmed'] for c in result['target_checks']))
    result['recorded_exit_code'] = metadata['recorded_exit_code']
    if result['recorded_exit_code']:
        result['rebuild_required'] = True
    result.update(status='draft',cell_id=request['cell']['cell_id'],actor=request['actor'],case_id=request['case']['case_id'],
        situation_confirmed=bool(result['setup_confirmed'] and all(c['matched'] and c['physical_cause_confirmed'] for c in result['target_checks'])),
        attempt_directory=str(directory))
    assert_current(dependency_hashes or {})
    return result


def verified_closed_video_recovery(directory, case, observed):
    """Accept an independent no-driving receipt only for closed null-mux failures."""
    from .completion import verify, sha
    from .store import digest
    from .validation import recording_evidence
    directory = Path(directory)
    receipt_path = directory / 'offline_recovery.json'
    if not receipt_path.is_file():
        raise ValueError('No verified offline recovery receipt')
    receipt = json.loads(receipt_path.read_text())
    binding = observed.get('completion', {}).get('binding')
    if not binding or binding.get('specification_hash') != digest(case):
        raise ValueError('Offline recovery does not bind the frozen case')
    source = verify(directory, binding)
    if source.get('completion') != observed.get('completion'):
        raise ValueError('Stored execution differs from the original completion')
    if Path(receipt.get('original_result', '')).resolve() != (directory / 'result.json').resolve():
        raise ValueError('Offline recovery names another result')
    if not all(source.get(key) for key in ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('Offline recovery cannot confirm a physical failure')
    checks = source.get('target_checks', [])
    if not checks or not all(check.get('matched') and check.get('physical_cause_confirmed') for check in checks):
        raise ValueError('Offline recovery cannot replace failed physical targets')
    if receipt.get('projected_target_checks') != checks:
        raise ValueError('This recovery path cannot alter target comparisons')
    errors = source.get('errors', [])
    if not errors or any(error.get('type') != 'CalledProcessError' or "'ffmpeg'" not in error.get('message','') or "'-f', 'null', '-'" not in error.get('message','') for error in errors):
        raise ValueError('Only the diagnosed post-recording null-mux check is recoverable here')
    if any(value is True or isinstance(value,list) and bool(value) for value in source.get('physical_failure_flags',{}).values()):
        raise ValueError('Recorded physical failure remains unaccepted')
    if not all(receipt.get(key) for key in ('frame_join_confirmed','physical_targets_confirmed','decoder_passed','maneuver_completed')):
        raise ValueError('Incomplete offline recovery evidence')
    trace = [json.loads(line) for line in (directory / 'trace.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (directory / source['video_frame_map_reference']).read_text().splitlines()]
    capture = json.loads((directory / 'capture/manifest.json').read_text())
    count = len(trace)
    if not count or count != len(mapping) or count != receipt.get('frame_count') or count != capture.get('frames') or not capture.get('extraction_confirmed'):
        raise ValueError('Offline recovery frame inventory differs from original capture')
    if any(row.get('video_frame') != i or row.get('carla_frame') != point['frame'] or abs(row['time_s']-point['time_s']) > 1e-6 for i,(row,point) in enumerate(zip(mapping,trace))):
        raise ValueError('Original video/trace join changed')
    refs = source.get('video_references', [])
    if receipt.get('verified_video_references') != refs or not refs:
        raise ValueError('Offline recovery video membership changed')
    for ref in refs:
        validation = next((v for v in source.get('video_validation', []) if v.get('reference') == ref), None)
        if not validation or sha(directory / ref) != validation.get('sha256') or int(validation['ffprobe']['streams'][0]['nb_read_frames']) != count:
            raise ValueError('Original decoded-video receipt is missing or changed')
    def artifact_path(value):
        path = (directory / value).resolve()
        if directory.resolve() not in path.parents or not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing original recording evidence')
        return path
    if source['recording_description'] != case['recording_description']:
        raise ValueError('Offline recovery changes the recording contract')
    recording_evidence(source,case['recording_description'],artifact_path,case.get('sweep_measurements', []))
    decoder = json.loads((directory / 'traffic_spec/adapter_report.json').read_text()).get('decoder_validation', {})
    if not decoder.get('passed') or 'full_core=true' not in decoder.get('output', ''):
        raise ValueError('Full Core decoder receipt required')
    return {'offline_recovery':str(receipt_path),'original_execution_exit_code':source.get('recorded_exit_code'),
        'original_execution_errors':errors,'recovery_source_result_sha256':sha(directory / 'result.json'),
        'recovery_receipt_sha256':sha(receipt_path),'rebuild_required':False}
