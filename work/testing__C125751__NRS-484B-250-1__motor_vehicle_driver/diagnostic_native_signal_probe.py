"""Probe the native signal source path using a sealed synthetic six-frame attempt.

The signal group is diagnostic. This proof may narrow Core integration gaps,
but it cannot establish original reviewed site facts or physical capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from case_protocol import ASSIGNMENT
from diagnostic_core_atom_contract import project_diagnostic


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source: Path, scratch: Path, manifest: Path, validator: Path) -> dict:
    source = source.resolve()
    scratch = scratch.resolve()
    if scratch.exists():
        raise ValueError('Use a fresh scratch directory for each probe')
    scratch.mkdir(parents=True)
    attempt = scratch / 'attempt'
    shutil.copytree(source, attempt)
    projection = project_diagnostic(attempt)
    evidence_path = attempt / 'capture/evidence.jsonl'
    rows = [json.loads(line) for line in evidence_path.read_text().splitlines()]
    if len(rows) != len(projection):
        raise ValueError('Synthetic graph/evidence frame count mismatch')
    for row, scene in zip(rows, projection):
        observed = row['original_observations']
        frame, time_s = observed['frame'], observed['time_s']
        if row['original_frame'] != frame or scene['t'] != time_s:
            raise ValueError('Synthetic signal frame/time mismatch')
        indication = scene['devices'][0]['indications'][0]
        state = {'circular_red': 'Red', 'circular_yellow': 'Yellow',
                 'circular_green': 'Green', 'dark': 'Off'}[indication]
        device = {'actor_id': 51, 'blueprint': 'traffic.traffic_light', 'state': state,
                  'position_m': [0.0, 0.0, 4.0],
                  'light_box_method': 'TrafficLight.get_light_boxes',
                  'light_boxes': [{'light_box_index': 0}]}
        observed['devices'] = [device]
        observed['control_actor_inventory'] = {
            'frame': frame, 'time_s': time_s, 'method': 'World.get_actors',
            'prefix': 'traffic.', 'complete': True, 'actor_ids': [51]}
        graph_path = attempt / f'capture/native/graphs/base/{frame:08d}.adapter.json'
        graph = json.loads(graph_path.read_text())
        graph['metadata']['observed_evidence'] = observed
        graph['nodes'].append({'id': 'diagnostic-signal-51-0', 'attributes': {
            'sem_class': 'traffic.traffic_light', 'carla_id': 51, 'entity_id': 51,
            'carla_light_box_index': 0,
            'signal_group_source': 'TrafficLight.get_light_boxes',
            'original_device_observation': device, 'vertex': [0.0, 0.0, 4.0],
            'light_state': state}})
        graph_path.write_text(json.dumps(graph, separators=(',', ':')) + '\n')
    evidence_path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    before = {p.relative_to(attempt).as_posix(): sha(p) for p in attempt.rglob('*') if p.is_file()}
    repo = Path(__file__).resolve().parents[2]
    output = scratch / 'saved'
    command = [str(repo / '.venv-cpu/bin/python'), str(repo / 'runtime.py'),
               'process-saved', '--manifest', str(manifest.resolve()),
               '--case', ASSIGNMENT + '__precedence', '--attempt', str(attempt),
               '--output', str(output), '--library', str(repo / 'runtime/library'),
               '--validator', str(validator.resolve())]
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch / 'pipeline-output')
    env['TMPDIR'] = str(scratch)
    completed = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True)
    (scratch / 'process-saved.log').write_text(completed.stdout + completed.stderr)
    after = {p.relative_to(attempt).as_posix(): sha(p) for p in attempt.rglob('*') if p.is_file()}
    feedback_path = output / 'v0001/feedback.json'
    feedback = json.loads(feedback_path.read_text()) if feedback_path.is_file() else {}
    expected = "Mandatory observation coverage incomplete: ['st.intersection', 'st.lane_enters']"
    if (completed.returncode == 0 or feedback.get('error') != expected or before != after
            or feedback.get('native_replay_requested') is not False):
        raise ValueError('Synthetic native signal integration did not isolate the two remaining atoms')
    trace = output / 'v0001/converted/trace.json'
    converted = json.loads(trace.read_text())['scenes'] if trace.is_file() else []
    if len(converted) != 6 or any(len(scene['devices']) != 1 or
                                  scene['devices'][0]['kind'] != 'traffic_signal' or
                                  scene['devices'][0]['indications'] != ['circular_green']
                                  for scene in converted):
        raise ValueError('Synthetic native traffic signal was not projected into Core')
    return {'diagnostic_fixture': True, 'frames': len(converted),
            'core_signal_projected': True, 'source_attempt_preserved': True,
            'expected_remaining_atoms': ['st.intersection', 'st.lane_enters'],
            'feedback_sha256': sha(feedback_path), 'converted_trace_sha256': sha(trace),
            'original_site_reviewed': False, 'physical_delivery_proven': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--validator', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.scratch, args.manifest, args.validator), sort_keys=True))
