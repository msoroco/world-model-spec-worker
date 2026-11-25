"""Run four selected saved paths against sealed, synthetic Native fixtures.

This is a software integration probe. No fixture is a reviewed original site or
physical capture, and no result here establishes statutory applicability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from case_protocol import ASSIGNMENT, SUFFIXES, EXPECTED


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')


def swap_other_later(history: dict) -> None:
    rows = history['frames']
    positions = [[0, -8], [0, -6], [0, -4], [0, 0], [0, 1], [0, 6]]
    for row, xy in zip(rows, positions):
        row['other']['xy_m'] = xy
        x, y = xy
        row['other']['body_vertices_xy_m'] = [
            [x - .2, y - .2], [x + .2, y - .2],
            [x + .2, y + .2], [x - .2, y + .2]]


def stage(base: Path, attempt: Path, offline: Path, suffix: str) -> None:
    shutil.copytree(base, attempt)
    for name in ('config.json', 'case-spec.json', 'construction.json'):
        shutil.copyfile(offline / name, attempt / name)
    case_id = ASSIGNMENT + '__' + suffix
    history_path = attempt / 'signal-history.json'
    history = json.loads(history_path.read_text())
    if suffix == 'other_later':
        swap_other_later(history)
    if suffix == 'signal_red':
        for index, row in enumerate(history['frames']):
            row['ego_light_readback'] = 'Red' if index < 2 else 'Green'
    response = EXPECTED[suffix][2]
    for row in history['frames']:
        row['ego_next_tick_request'] = 'proceed' if response == 'advance' else 'yield_then_proceed'
    write(history_path, history)
    packet_path = attempt / 'signal-packet.json'
    packet = json.loads(packet_path.read_text())
    packet['case_id'] = case_id
    packet['payload_sha256'] = sha(history_path)
    write(packet_path, packet)
    inventory_path = attempt / 'acquisition.json'
    inventory = json.loads(inventory_path.read_text())
    for name in ('signal-history.json', 'signal-packet.json'):
        inventory[name]['sha256'] = sha(attempt / name)
    write(inventory_path, inventory)
    native_manifest = attempt / 'capture/manifest.json'
    manifest = json.loads(native_manifest.read_text())
    manifest['case_id'] = case_id
    write(native_manifest, manifest)
    if suffix == 'signal_red':
        evidence_path = attempt / 'capture/evidence.jsonl'
        evidence = [json.loads(line) for line in evidence_path.read_text().splitlines()]
        for index, row in enumerate(evidence):
            state = 'Red' if index < 2 else 'Green'
            observed = row['original_observations']
            observed['devices'][0]['state'] = state
            graph_path = attempt / f"capture/native/graphs/base/{row['original_frame']:08d}.adapter.json"
            graph = json.loads(graph_path.read_text())
            graph['metadata']['observed_evidence'] = observed
            for node in graph['nodes']:
                if node['attributes'].get('sem_class') == 'traffic.traffic_light':
                    node['attributes']['light_state'] = state
                    node['attributes']['original_device_observation']['state'] = state
            write(graph_path, graph)
        evidence_path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                         for row in evidence))


def run(base: Path, offline_root: Path, scratch: Path, manifest: Path,
        validator: Path) -> dict:
    repo = Path(__file__).resolve().parents[2]
    base, offline_root = base.resolve(), offline_root.resolve()
    scratch, manifest, validator = scratch.resolve(), manifest.resolve(), validator.resolve()
    if scratch.exists():
        raise ValueError('Use a fresh .runtime-work scratch directory')
    scratch.mkdir(parents=True)
    receipts = []
    for suffix in SUFFIXES:
        attempt = scratch / suffix / 'attempt'
        attempt.parent.mkdir()
        stage(base, attempt, offline_root / suffix, suffix)
        before = {p.relative_to(attempt).as_posix(): sha(p)
                  for p in attempt.rglob('*') if p.is_file()}
        output = scratch / suffix / 'saved'
        command = [str(repo / '.venv-cpu/bin/python'), str(repo / 'runtime.py'),
                   'process-saved', '--manifest', str(manifest),
                   '--case', ASSIGNMENT + '__' + suffix, '--attempt', str(attempt),
                   '--output', str(output), '--library', str(repo / 'runtime/library'),
                   '--validator', str(validator)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'pipeline-output'),
                   TMPDIR=str(scratch))
        completed = subprocess.run(command, cwd=repo, env=env,
                                   capture_output=True, text=True)
        (scratch / suffix / 'process-saved.log').write_text(
            completed.stdout + completed.stderr)
        after = {p.relative_to(attempt).as_posix(): sha(p)
                 for p in attempt.rglob('*') if p.is_file()}
        processing_path = output / 'v0001/processing.json'
        feedback_path = output / 'v0001/feedback.json'
        processing = json.loads(processing_path.read_text()) if processing_path.is_file() else {}
        feedback = json.loads(feedback_path.read_text()) if feedback_path.is_file() else {}
        report_path = output / 'v0001/analysis-report.json'
        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
        adapter_path = output / 'v0001/converted/adapter_report.json'
        adapter = json.loads(adapter_path.read_text()) if adapter_path.is_file() else {}
        negative_attempt = scratch / suffix / 'missing-source-attempt'
        shutil.copytree(attempt, negative_attempt)
        (negative_attempt / 'signal-history.json').unlink()
        negative_output = scratch / suffix / 'missing-source-saved'
        negative_command = command.copy()
        negative_command[negative_command.index(str(attempt))] = str(negative_attempt)
        negative_command[negative_command.index(str(output))] = str(negative_output)
        negative_run = subprocess.run(negative_command, cwd=repo, env=env,
                                      capture_output=True, text=True)
        (scratch / suffix / 'missing-source.log').write_text(
            negative_run.stdout + negative_run.stderr)
        negative_feedback_path = negative_output / 'v0001/feedback.json'
        negative_feedback = (json.loads(negative_feedback_path.read_text())
                             if negative_feedback_path.is_file() else {})
        missing_rejected = (negative_run.returncode != 0 and
                            'signal-history.json' in negative_feedback.get('error', ''))
        receipts.append({'case_id': ASSIGNMENT + '__' + suffix,
                         'exit_code': completed.returncode,
                         'passed': processing.get('passed'),
                         'feedback_error': feedback.get('error'),
                         'source_attempt_preserved': before == after,
                         'atom_gaps': adapter.get('atom_coverage', {}).get('missing'),
                         'analysis_case_id': report.get('case_id'),
                         'missing_source_rejected': missing_rejected,
                         'missing_source_error': negative_feedback.get('error'),
                         'diagnostic_fixture': True,
                         'original_site_reviewed': False,
                         'physical_delivery_proven': False})
    return {'cases': receipts, 'diagnostic_fixture': True,
            'production_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--offline-root', required=True, type=Path)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--validator', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.base, args.offline_root, args.scratch,
                         args.manifest, args.validator), sort_keys=True))
