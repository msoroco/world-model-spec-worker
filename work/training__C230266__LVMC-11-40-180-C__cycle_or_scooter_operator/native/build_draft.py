"""Build two exact unselected CPU bundles from this assignment's sources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = []
    all_case_ids=[ASSIGNMENT+'__'+suffix for suffix in ('probe_a','probe_b','probe_c')]
    for suffix, signal, pause in (('probe_a', 80, True), ('probe_b', None, True),
                                  ('probe_c', 80, False)):
        case = ASSIGNMENT + '__' + suffix
        channels=[{'name':'rider_and_pedestrian_footprints','unit':'m',
                   'sampling_rate_hz':20,'source':'original Native transforms and bounding boxes'},
                  {'name':'pedestrian_location_audio','unit':'PCM s16le',
                   'sampling_rate_hz':8000,'source':'live microphone at pedestrian position'},
                  {'name':'sidewalk_map_context','unit':'Native map',
                   'sampling_rate_hz':20,'source':'OpenDRIVE and Native lane readback'},
                  {'name':'four_source_views','unit':'RGB frame',
                   'sampling_rate_hz':20,'source':'four synchronized original cameras'}]
        description={'channels':channels,
                     'limitations':['Original microphone position, sound identity, device class and legal audibility need independent review']}
        config = {'case_id': case, 'selected_case_id': case,
                  'cell_id': 'C230266', 'law_id': 'LVMC-11-40-180-C',
                  'actor': 'cycle_or_scooter_operator', 'duration_s': 30,
                  'rate_hz': 20, 'device_blueprint_filter': 'vehicle.diamondback.century',
                  'pedestrian_blueprint_filter': 'walker.pedestrian.*',
                  'signal_frame': signal, 'pause_window_frames': [80, 110] if pause else [0, 0],
                  'pedestrian_microphone': {'location': 'pedestrian_actor',
                                            'sampling': 'synchronized_original_audio_required',
                                            'alsa_device_env':'C230266_MIC_ALSA_DEVICE'},
                  'rider_speaker_alsa_device_env':'C230266_SPEAKER_ALSA_DEVICE' if signal is not None else None,
                  'target_request':{'pause_requested':pause,'signal_requested':signal is not None},
                  'supported_case_ids':all_case_ids,
                  'recording_description':description,
                  'cameras': [{'name': name, 'width': 1920 if i==0 else 1280,
                               'height': 1080 if i==0 else 720,
                               'pose_strategy':'fixed_sidewalk_wide' if i==0 else 'fixed_sidewalk_detail',
                               'fov_deg':75}
                              for i,name in enumerate(('overview','approach','reference_corner','driver_reference'))],
                  'required_atoms': ['ru.pedestrian', 'kin.position', 'kin.speed'],
                  'source_packets': []}
        files = []
        for source, target in ((NATIVE/'runner.py', 'runner.py'),
                               (NATIVE/'audio_source.py', 'audio_source.py'),
                               (NATIVE/'measure_sidewalk.py', 'measure_sidewalk.py'),
                               (NATIVE/'finalize.py', 'finalize.py'),
                               (NATIVE/'road.xodr', 'road.xodr'),
                               (NATIVE/'tests/test_offline.py', 'tests/test_offline.py'),
                               (NATIVE/'tests/test_saved.py', 'tests/test_saved.py')):
            files.append({'path': target, 'content': source.read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        contract={'format':'worker-measurement-contract','case_id':case,
                  'requirements':[{'disposition_index':index,'requirement':requirement,
                      'source':'LVMC 11.40.180(C)','output_key':key,'method':method,
                      'value_type':'object','kind':'measured','inputs':[
                          'sidewalk-actors.jsonl','video_frames.jsonl','camera-frames.jsonl',
                          'pedestrian-microphone.json','pedestrian-microphone-frames.jsonl',
                          'sidewalk-map-readback.json','road.xodr']}
                      for index,requirement,key,method in (
                          (0,'Covered bicycle on sidewalk','covered_device_sidewalk','device_and_sidewalk'),
                          (1,'Yield right-of-way to pedestrian','pedestrian_priority_response','yield_observation'),
                          (2,'Audible signal before overtaking pedestrian','audible_signal_order','source_audio_order'))],
                  'negative':{'remove':['pedestrian-microphone.json'],
                              'error_contains':'Missing required source: pedestrian-microphone.json'}}
        files.append({'path':'measurement-contract.json',
                      'content':json.dumps(contract,indent=2)+'\n'})
        dump(ROOT/('measurement-'+suffix+'.json'),contract)
        construction = {'case_id': case, 'cell_id': 'C230266',
                        'law_id': 'LVMC-11-40-180-C', 'actor': 'cycle_or_scooter_operator',
                        'entrypoint': 'runner.py', 'files': files,
                        'recording_description': description,
                        'measurement_plan':{'method':'saved_source_join',
                                            'entrypoint':'finalize.py'},
                        'static_checks':['test_offline','test_saved'],
                        'termination_rules':['600 Native frames or fail closed on missing source'],
                        'mechanisms':['Native bicycle/pedestrian actor capture','live microphone PCM acquisition'],
                        'status': 'unselected_exact_cpu_draft'}
        path = ROOT/'native-draft'/suffix/'construction.json'
        dump(path, construction)
        entries.append({'case_id': case, 'kind': 'draft_not_selected',
                        'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': sha(path), 'candidates': [],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Native device motion and pedestrian-location audio not yet tested'}})
    dump(ROOT/'native-draft-manifest.json', {
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': ASSIGNMENT, 'status': 'draft_not_selected',
        'cases': entries, 'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
