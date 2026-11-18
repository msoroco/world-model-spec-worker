"""Independent C24753 audit of retained Native sources and named camera streams."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('signal_context.json', 'signal_state.jsonl', 'participant_state.jsonl',
           'video_frames.jsonl', 'trace.jsonl')
BRANCHES = {
    'east_cautious_proxy': ('east', 3.0, True),
    'east_faster_proxy': ('east', 7.0, True),
    'east_no_crossing': ('east', 3.0, False),
    'west_cautious_proxy': ('west', 3.0, True),
}

def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def audit_sources(attempt, report):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    for name in ('config.json', *SOURCES):
        if not (root/name).is_file():
            raise ValueError('Missing audited original source: '+name)
    config = json.loads((root/'config.json').read_text())
    branch = config.get('case_branch')
    if branch not in BRANCHES or report.get('case_id') != config.get('selected_case_id'):
        raise ValueError('Audit selects another exact heavy case')
    direction, speed_target, crossing_expected = BRANCHES[branch]
    if config.get('target_speed_mps') != speed_target:
        raise ValueError('Exact heavy speed target changed')
    if report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Unreviewed physical or legal acceptance claimed')
    context = json.loads((root/'signal_context.json').read_text())
    if (context.get('selected_direction') != direction or
        context.get('heavy_blueprint_id') != config.get('heavy_blueprint_id') or
        not context.get('official_control_source') or not context.get('opendrive_id')):
        raise ValueError('Original governed heavy context differs')
    measurement = report['measurements']['flashing_yellow_heavy']
    source_hashes = measurement.get('sources', {})
    if set(source_hashes) != set(SOURCES) or any(
        _hash(root/name) != checksum for name, checksum in source_hashes.items()
    ):
        raise ValueError('Analysis source hash differs from original acquisition')
    frames, signals, parties, trace = (_rows(root/name) for name in
        ('video_frames.jsonl','signal_state.jsonl','participant_state.jsonl','trace.jsonl'))
    if len(frames) < 2 or len({len(frames),len(signals),len(parties),len(trace)}) != 1:
        raise ValueError('Original source frame count differs')
    transitions = 0
    prior_state = None
    ego_id = crossing_id = None
    speeds = []
    for i, (frame, signal, party, motion) in enumerate(zip(frames,signals,parties,trace)):
        identity = (frame.get('carla_frame'), frame.get('time_s'))
        if frame.get('video_frame') != i or any(
            (row.get('frame'),row.get('time_s')) != identity
            for row in (signal,party,motion)
        ):
            raise ValueError('Original frame/time join differs')
        state = str(signal.get('native_light_state','')).removeprefix('TrafficLightState.')
        if (signal.get('light_actor_id') != context.get('light_actor_id') or
            signal.get('opendrive_id') != context.get('opendrive_id') or
            state not in ('Yellow','Off') or
            signal.get('yellow_commanded') is not (state == 'Yellow')):
            raise ValueError('Original governed signal readback differs')
        current = state == 'Yellow'
        if prior_state is not None:
            transitions += current != prior_state
        prior_state = current
        ego, crossing = party.get('ego'), party.get('crossing')
        if (not isinstance(ego,dict) or ego.get('vehicle_class') != 'heavy_vehicle' or
            ego.get('blueprint_id') != config['heavy_blueprint_id'] or
            type(ego.get('actor_id')) is not int):
            raise ValueError('Original heavy participant missing')
        if ego_id is None:
            ego_id = ego['actor_id']
        if ego['actor_id'] != ego_id:
            raise ValueError('Original heavy identity changed')
        if crossing_expected:
            if not isinstance(crossing,dict) or type(crossing.get('actor_id')) is not int:
                raise ValueError('Original crossing participant missing')
            if crossing_id is None:
                crossing_id = crossing['actor_id']
            if crossing['actor_id'] != crossing_id:
                raise ValueError('Original crossing identity changed')
        elif crossing is not None:
            raise ValueError('Unexpected crossing participant in empty case')
        if type(ego.get('speed_mps')) not in (int,float) or ego['speed_mps'] < 0:
            raise ValueError('Original heavy speed missing')
        speeds.append(ego['speed_mps'])
    measured = measurement['value']
    if (transitions < 1 or transitions != measured.get('native_transitions') or
        crossing_expected is not measured.get('crossing_present') or
        speeds != measured.get('ego_speed_samples_mps')):
        raise ValueError('Analysis differs from independent original-source measurement')
    if (measured.get('lens_pixel_visibility') != 'unverified' or
        measured.get('official_device_status') != 'premise_unverified' or
        measured.get('legal_caution_judgment') != 'unresolved'):
        raise ValueError('Unreviewed source fact asserted by analysis')
    return {'case_id':config['selected_case_id'],'frames':len(frames),
            'direction':direction,'crossing_present':crossing_expected,
            'source_hashes':source_hashes,'transitions':transitions,
            'speed_samples_mps':speeds}

def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    sources = audit_sources(root, report)
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        path = root/(name+'.mkv')
        if not path.is_file():
            raise ValueError('Missing named original camera: '+name)
        decode = decoder(path, sources['frames'],
                         mapping_sha256=_hash(root/'video_frames.jsonl'))
        if decode.get('frames') != sources['frames']:
            raise ValueError('Original camera full-decode frame count differs')
        cameras[name] = {'sha256':_hash(path),'decode':decode}
    return {'format':'worker-heavy-signal-source-audit',**sources,
            'camera_decodes':cameras,'native_source':True,
            'all_participants':True,'time_join':True,'full_video_decode':True,
            'actual_pixels':'decoded_sources_only','physical_completion':'unverified',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--analysis',required=True)
    args = parser.parse_args()
    receipt = audit_attempt(args.attempt,args.analysis)
    if receipt['case_id'] != args.case:
        raise ValueError('Audit command selects another exact case')
    print(json.dumps(receipt,sort_keys=True))
