"""Exercise pinned saved Core conversion with a synthetic junction source.

The map and its mocked native lane-section readback are diagnostic fixtures.
They do not represent the reviewed C125751 median opening or physical CARLA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from case_protocol import ASSIGNMENT
from original_observations import map_lane_topology


REQUIRED = {'dev.traffic_signal', 'st.intersection', 'st.lane_enters'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + '\n')


def stage(source: Path, target: Path, map_source: Path, *, complete: bool) -> None:
    shutil.copytree(source, target)
    shutil.copyfile(map_source, target / 'road.xodr')
    root = ET.fromstring((target / 'road.xodr').read_bytes())
    junctions = {int(road.get('id')): int(road.get('junction', '-1'))
                 for road in root.findall('road')}
    if not root.findall('junction') or not junctions:
        raise ValueError('Diagnostic junction map has no source topology')

    class DiagnosticNativeMap:
        def get_waypoint_xodr(self, road_id, lane_id, station):
            junction = junctions[road_id]
            return SimpleNamespace(road_id=road_id, section_id=0, lane_id=lane_id,
                                   is_junction=junction >= 0, junction_id=junction)

    topology = map_lane_topology(DiagnosticNativeMap(), target / 'road.xodr')
    if not topology['complete']:
        raise ValueError('Diagnostic lane-section readback incomplete')
    if not complete:
        topology['complete'] = False
    facts_path = target / 'capture/native_map_facts.json'
    facts = json.loads(facts_path.read_text())
    facts['native_lane_topology'] = topology
    write(facts_path, facts)
    manifest_path = target / 'capture/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['sources']['road.xodr'] = sha(target / 'road.xodr')
    manifest['native_map_facts']['sha256'] = sha(facts_path)
    write(manifest_path, manifest)


def process(repo: Path, attempt: Path, output: Path, manifest: Path,
            validator: Path, scratch: Path) -> tuple[int, dict]:
    command = [str(repo / '.venv-cpu/bin/python'), str(repo / 'runtime.py'),
               'process-saved', '--manifest', str(manifest),
               '--case', ASSIGNMENT + '__precedence', '--attempt', str(attempt),
               '--output', str(output), '--library', str(repo / 'runtime/library'),
               '--validator', str(validator)]
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch / 'pipeline-output')
    env['TMPDIR'] = str(scratch)
    completed = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True)
    (scratch / (output.name + '.log')).write_text(completed.stdout + completed.stderr)
    version = output / 'v0001'
    processing = version / 'processing.json'
    feedback = version / 'feedback.json'
    return completed.returncode, (json.loads(processing.read_text()) if processing.is_file()
                                  else json.loads(feedback.read_text()) if feedback.is_file() else {})


def run(source: Path, map_source: Path, scratch: Path,
        manifest: Path, validator: Path) -> dict:
    repo = Path(__file__).resolve().parents[2]
    source, map_source = source.resolve(), map_source.resolve()
    scratch, manifest, validator = scratch.resolve(), manifest.resolve(), validator.resolve()
    if scratch.exists():
        raise ValueError('Use a fresh scratch directory')
    scratch.mkdir(parents=True)
    positive_attempt = scratch / 'positive-attempt'
    stage(source, positive_attempt, map_source, complete=True)
    before = {p.relative_to(positive_attempt).as_posix(): sha(p)
              for p in positive_attempt.rglob('*') if p.is_file()}
    positive_output = scratch / 'positive-saved'
    exit_code, processing = process(repo, positive_attempt, positive_output,
                                    manifest, validator, scratch)
    after = {p.relative_to(positive_attempt).as_posix(): sha(p)
             for p in positive_attempt.rglob('*') if p.is_file()}
    adapter = positive_output / 'v0001/converted/adapter_report.json'
    trace = positive_output / 'v0001/converted/trace.json'
    if (exit_code or processing.get('passed') is not True or before != after
            or not adapter.is_file() or not trace.is_file()):
        raise ValueError('Diagnostic junction did not pass recorded-only conversion')
    report = json.loads(adapter.read_text())
    scenes = json.loads(trace.read_text())['scenes']
    if (len(scenes) != 6 or report.get('atom_coverage', {}).get('missing')
            or any(not any(r['kind'] == 'intersection' for r in scene['structures'])
                   or not any(r['kind'] == 'lane' and r.get('lane', {}).get('enters_intersection')
                              for r in scene['structures'])
                   or not any(d['kind'] == 'traffic_signal' and d.get('indications')
                              for d in scene['devices']) for scene in scenes)):
        raise ValueError('Diagnostic Core trace lacks one of the three source-shaped atoms')
    negative_attempt = scratch / 'negative-attempt'
    stage(source, negative_attempt, map_source, complete=False)
    negative_output = scratch / 'negative-saved'
    negative_exit, negative_feedback = process(repo, negative_attempt, negative_output,
                                               manifest, validator, scratch)
    if negative_exit == 0 or 'st.lane_enters' not in negative_feedback.get('error', ''):
        raise ValueError('Incomplete native lane scope was not rejected')
    return {'diagnostic_fixture': True, 'frames': len(scenes),
            'core_atoms': sorted(REQUIRED), 'positive_saved_exit_code': exit_code,
            'positive_atom_gaps': [], 'negative_missing_atom': 'st.lane_enters',
            'source_attempt_preserved': before == after,
            'map_sha256': sha(map_source), 'adapter_report_sha256': sha(adapter),
            'original_site_reviewed': False, 'actual_pixels_verified': False,
            'physical_delivery_proven': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--map', required=True, type=Path)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--validator', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.map, args.scratch, args.manifest,
                         args.validator), sort_keys=True))
