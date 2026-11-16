"""CPU comparison of observed-reference and generated-signal original-source paths."""
import argparse
import hashlib
import json
from pathlib import Path


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(reference, signaled):
    paths = [Path(reference), Path(signaled)]
    data = [json.loads(path.read_text()) for path in paths]
    source = [value['files'] for value in data]
    receipts = [json.loads(f['overtake_source_receipt.json']) for f in source]
    if not receipts[0]['case_id'].endswith('__observed_gives_way_holds_speed') or not receipts[1]['case_id'].endswith('__audible_signal_gives_way_holds_speed'):
        raise ValueError('Notice comparison exact identity differs')
    fixed = ('overtake_site_original.json', 'overtake_bodies_original.jsonl',
             'trace.jsonl', 'video_frames.jsonl', 'overview-frames.jsonl',
             'approach-frames.jsonl', 'reference_corner-frames.jsonl',
             'driver_reference-frames.jsonl')
    for name in fixed:
        if source[0][name] != source[1][name]:
            raise ValueError('Notice comparison fixed original source differs: ' + name)
        for index in (0, 1):
            if digest(source[index][name]) != receipts[index]['source_sha256'][name]:
                raise ValueError('Notice comparison source hash differs: ' + name)
    if data[0]['videos'] != data[1]['videos'] or data[0]['graphs'] != data[1]['graphs']:
        raise ValueError('Notice comparison fixed video or graph differs')
    bodies = rows(source[1]['overtake_bodies_original.jsonl'])
    commands = rows(source[1]['signal_command_original.jsonl'])
    envelope = rows(source[1]['signal_audio_envelope_original.jsonl'])
    if not len(bodies) == len(commands) == len(envelope) or len(bodies) < 3:
        raise ValueError('Notice comparison signal frame count differs')
    for name in ('signal_command_original.jsonl', 'signal_audio_envelope_original.jsonl'):
        if digest(source[1][name]) != receipts[1]['source_sha256'][name]:
            raise ValueError('Notice comparison signal source hash differs: ' + name)
    requested = []
    for body, command, sound in zip(bodies, commands, envelope):
        common = (body['frame'], body['time_s'], receipts[1]['overtaker_actor_id'])
        if tuple(command.get(k) for k in ('frame', 'time_s', 'overtaker_actor_id')) != common or tuple(sound.get(k) for k in ('frame', 'time_s', 'overtaker_actor_id')) != common:
            raise ValueError('Notice comparison original signal frame join differs')
        if sound.get('source_kind') != 'generated_signal_envelope' or sound.get('generated_rms') != (0.6 if command.get('horn_command_requested') is True else 0.0):
            raise ValueError('Notice comparison generated signal envelope differs')
        if command['horn_command_requested']:
            requested.append(body['frame'])
    if len(requested) < 2:
        raise ValueError('Notice comparison signal command absent')
    return {'format':'worker-notice-alternative-comparison','comparison_id':'notice_alternative',
            'case_ids':[x['case_id'] for x in receipts],
            'source_sha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
            'fixed_motion_camera_and_graphs':True,'frames':len(bodies),
            'signal_command_frames':requested,'generated_envelope_verified':True,
            'acoustic_propagation_confirmed':None,'subjective_hearing_confirmed':None,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('reference');parser.add_argument('signaled');parser.add_argument('--output',required=True)
    args=parser.parse_args();Path(args.output).write_text(json.dumps(audit(args.reference,args.signaled),indent=2)+'\n')

if __name__=='__main__':main()
