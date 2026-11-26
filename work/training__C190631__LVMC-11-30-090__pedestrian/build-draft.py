"""Build source-bound roadway walking CPU draft from authored Native files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = (('probe_01', 'sidewalk'), ('probe_02', 'roadway'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    entries = []
    for suffix, surface in CASES:
      case = HERE.name + '__' + suffix
      config = {'case_id': case, 'selected_case_id': case,
              'supported_case_ids': [HERE.name + '__' + s for s, _ in CASES], 'candidate_id': 'primary',
              'law_id': 'LVMC-11-30-090', 'cell_id': 'C190631', 'actor': 'pedestrian',
              'walking_surface': surface,
              'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
              'source_packets': [], 'case': {'case_id': case},
              'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                           'height': 1080 if name == 'overview' else 720}
                          for name in ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'recording_description': {'channels': [
                  {'name': term, 'unit': 'source observation', 'sampling_rate_hz': 20,
                   'method': 'original Native walker pose/footprint and surveyed map',
                   'time_window': '600 frames / 30 s',
                   'reference_frame': 'original C190631 pedestrian and overpass roads',
                   'uncertainty': 'Native provision/purpose and pixels need local review'}
                  for term in ('ru.subject', 'st.sidewalk', 'st.roadway',
                               'rel.occupies', 'kin.heading', 'kin.path_length')],
                  'limitations': ['Native survey and walker/camera execution require CARLA verification']},
              'status': 'cpu_draft_not_delivery_prepared'}
      files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
             for name in ('runner.py', 'geometry.py', 'measure.py', 'finalize.py', 'tests/test_native.py')]
      files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
      proposal = {'case_id': case, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                'recording_description': config['recording_description'],
                'measurement_plan': {'entrypoint': 'finalize.py',
                                     'required_sources': ['pedestrian-poses.jsonl', 'surface-geometry.json'],
                                     'status': 'source_bound_cpu_draft'},
                'static_checks': ['100 m elevated OpenDRIVE with driving, shoulder and sidewalk lanes', 'four camera plan',
                                  '600-frame 20 Hz timing'],
                'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                'mechanisms': [f'walker follows adjacent {surface}',
                               'original poses and surface geometry measured independently'],
                'status': 'partial_native_execution_cpu_checked_physical_unverified'}
      path = HERE / 'draft-roadway' / suffix / 'primary/construction.json'
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(json.dumps(proposal, indent=2) + '\n')
      entries.append({'case_id': case, 'kind': 'delivery',
                      'construction': str(path.relative_to(HERE)),
                      'construction_sha256': sha(path),
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Overpass surface and walker path require Native readback'},
                      'candidates': [], 'measurement_procedure': {'entrypoint': 'finalize.py'},
                      'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial',
                'cases': entries}
    (HERE / 'draft-roadway-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': [(e['case_id'], e['construction_sha256']) for e in entries],
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
