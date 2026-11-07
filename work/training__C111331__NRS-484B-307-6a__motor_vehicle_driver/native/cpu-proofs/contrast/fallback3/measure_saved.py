"""Recompute signal-at-entry evidence from joined saved sources."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(source_dir, case_id, candidate_id):
    source_dir = Path(source_dir)
    native = rows(source_dir / 'native_samples.jsonl')
    video = rows(source_dir / 'video_frames.jsonl')
    if len(native) != 480 or len(video) != 480:
        raise ValueError('Saved 480-frame profile differs')
    entry = None
    provenance = native[0]['source_kind']
    phases = []
    signal_ids = set()
    for i, (n, v) in enumerate(zip(native, video)):
        if n['request_index'] != i or v['video_frame'] != i or n['native_frame'] != v['native_frame']:
            raise ValueError('Native/video frame join differs')
        if abs(n['time_s'] - v['time_s']) > .001 or abs(n['time_s'] - i / 20) > .051:
            raise ValueError('Native/video time join differs')
        if n['source_kind'] not in ('synthetic_cpu_native_observation', 'original_native_observation') or n['source_kind'] != provenance:
            raise ValueError('Saved source provenance differs')
        phase = n['observed_signal_state'].lower().rsplit('.', 1)[-1]
        if phase not in ('green', 'yellow', 'red'):
            raise ValueError('Observed Native signal phase missing')
        phases.append(phase)
        signal_ids.add(n['signal_actor_id'])
        body = n['native_body_xy_m']
        if len(body) != 4 or any(len(p) != 2 for p in body):
            raise ValueError('Native body footprint differs')
        if entry is None and min(p[1] for p in body) <= 7.0:
            entry = i
    if len(signal_ids) != 1 or entry is None:
        raise ValueError('Native signal actor or body entry absent')
    red = next((i for i, phase in enumerate(phases) if phase == 'red'), None)
    yellow = next((i for i, phase in enumerate(phases) if phase == 'yellow'), None)
    if yellow is None or red is None or yellow >= red or any(p != 'green' for p in phases[:yellow]) or any(p != 'yellow' for p in phases[yellow:red]) or any(p != 'red' for p in phases[red:]):
        raise ValueError('Observed signal sequence differs')
    return {'format': 'c111331-saved-signal-entry-measurement-v1',
            'case_id': case_id, 'candidate_id': candidate_id,
            'source_kind': provenance,
            'sources': {'native_samples.jsonl': sha(source_dir / 'native_samples.jsonl'),
                        'video_frames.jsonl': sha(source_dir / 'video_frames.jsonl')},
            'observed_signal_actor_id': next(iter(signal_ids)),
            'observed_yellow_start_frame': yellow, 'observed_red_start_frame': red,
            'observed_full_body_entry_frame': entry,
            'observed_signal_phase_at_entry': phases[entry],
            'entry_to_red_margin_frames': red - entry,
            'frame_bracket_uncertainty_s': .05,
            'physical_native_evidence': provenance == 'original_native_observation',
            'original_pixel_visibility_verified': False,
            'statutory_verdict_claimed': False}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--source-dir', required=True)
    p.add_argument('--case-id', required=True)
    p.add_argument('--candidate-id', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = measure(a.source_dir, a.case_id, a.candidate_id)
    Path(a.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
