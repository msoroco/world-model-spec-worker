"""Independent source-bound comparison checks for sidewalk CPU diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = {'signal': ('probe_a', 'probe_b', 'signal_frame', 'pause_window_frames'),
         'yield': ('probe_a', 'probe_c', 'pause_window_frames', 'signal_frame')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config(suffix):
    construction = json.loads((HERE / 'native-draft' / suffix / 'construction.json').read_text())
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path'] == 'config.json'))


def check(pair, negative=False):
    a, b, changed, fixed = PAIRS[pair]
    ca, cb = config(a), config(b)
    if negative:
        cb[fixed] = None
    if ca[changed] == cb[changed]:
        raise ValueError('Comparison does not vary requested ' + changed)
    if ca[fixed] != cb[fixed]:
        raise ValueError('Comparison changed fixed ' + fixed)
    allowed = {'case_id', 'selected_case_id', 'signal_frame',
               'pause_window_frames', 'target_request', 'rider_speaker_alsa_device_env'}
    if {k: v for k, v in ca.items() if k not in allowed} != {
            k: v for k, v in cb.items() if k not in allowed}:
        raise ValueError('Comparison changed frozen setup')
    source_a = HERE / 'diagnostic-source' / a
    source_b = HERE / 'diagnostic-source' / b
    actor_a = source_a / 'sidewalk-actors.jsonl'
    actor_b = source_b / 'sidewalk-actors.jsonl'
    audio_a = source_a / 'pedestrian-microphone.hex'
    audio_b = source_b / 'pedestrian-microphone.hex'
    for path in (actor_a, actor_b, audio_a, audio_b):
        if not path.is_file():
            raise ValueError('Missing comparison source: ' + str(path))
    if pair == 'signal' and sha(actor_a) != sha(actor_b):
        raise ValueError('Signal comparison changed actor trajectory')
    if pair == 'signal' and sha(audio_a) == sha(audio_b):
        raise ValueError('Signal comparison lacks microphone difference')
    if pair == 'yield' and sha(actor_a) == sha(actor_b):
        raise ValueError('Yield comparison lacks actor trajectory difference')
    if pair == 'yield' and sha(audio_a) != sha(audio_b):
        raise ValueError('Yield comparison changed microphone source')
    comparison_id = HERE.name + ('__comparison' if pair == 'signal'
                                 else '__yield_comparison')
    return {'format': 'c230266-sidewalk-comparison-cpu-v1',
            'comparison_id': comparison_id,
            'case_ids': [HERE.name + '__' + a, HERE.name + '__' + b],
            'changed_request_key': changed, 'fixed_request_key': fixed,
            'actor_source_sha256': [sha(actor_a), sha(actor_b)],
            'microphone_source_sha256': [sha(audio_a), sha(audio_b)],
            'source_originality': 'synthetic_fixture',
            'original_native_outcome_reviewed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', choices=tuple(PAIRS), required=True)
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(args.pair, args.negative)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'pair': args.pair, 'checked': True}))
