"""Prove generic saved motion/lifecycle branches for six planned sweep cases."""
import copy
import hashlib
import json
from pathlib import Path

from prove_motion_outcome import classify, lifecycle, EVENTS

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    fixture_path = HERE / 'selected-reference-fixture.json'
    fixture = json.loads(fixture_path.read_text())
    files = fixture['files']
    base_trace = [json.loads(x) for x in files['trace.jsonl'].splitlines()]
    base_evidence = [json.loads(x) for x in files['capture/evidence.jsonl'].splitlines()]
    base_graphs = fixture['graphs']
    provenance = json.loads(files['acquisition-provenance.json'])
    for entry in manifest['cases']:
        if '__judgment-' not in entry['case_id']:
            continue
        folder = HERE / 'sweep-cases' / entry['case_id'] / 'physical'
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            trace, evidence, graphs = (copy.deepcopy(base_trace),
                                       copy.deepcopy(base_evidence), copy.deepcopy(base_graphs))
            if kind == 'incomplete_motion':
                for row, event, graph in zip(trace, evidence, graphs):
                    row['position_m'][0] = 0.0
                    row['position']['x'] = 0.0
                    row['velocity_mps'][0] = 0.0
                    row['acceleration_mps2'][0] = 0.0
                    row['speed_mps'] = 0.0
                    row['speed_mph'] = 0.0
                    event['ego']['position_m'][0] = 0.0
                    event['ego']['speed_mps'] = 0.0
                    event['world']['road_projection']['s_m'] = 0.0
                    for index, vertex in enumerate(event['ego']['body_vertices_m']):
                        vertex[0] = -2.0 if index < 4 else 2.0
                    graph['nodes'][0]['attributes']['vertex'][0] = 0.0
                    for index, vertex in enumerate(graph['nodes'][0]['attributes']['threedbbox']):
                        vertex[0] = -2.0 if index < 4 else 2.0
            elif kind == 'missing_evidence':
                trace.pop()
            result = classify(trace, evidence, graphs, provenance)
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if result['physical_checks']['maneuver']['status'] != expected:
                raise ValueError('Physical diagnostic branch differs: ' + kind)
            if classify(trace, evidence, graphs, {})['physical_checks']['maneuver']['status'] != 'unverified':
                raise ValueError('Missing provenance was accepted')
            result.update({'case_id': entry['case_id'],
                           'construction_sha256': entry['construction_sha256'],
                           'source_fixture_spec_sha256': sha(fixture_path),
                           'source_fixture_case_id': provenance['case_id'],
                           'source_fixture_reused_for_generic_cpu_motion_test': True,
                           'sweep_target_realization_verified': False,
                           'fixture_mutation': kind})
            result_path = folder / (kind + '.json')
            log_path = folder / (kind + '.log')
            write(result_path, result)
            log_path.write_text(json.dumps({'case_id': entry['case_id'],
                                            'fixture_kind': kind, 'status': expected,
                                            'synthetic_only': True}) + '\n')
            fixtures.append({'kind': kind,
                             'command': 'prove_sweep_physical.py --case ' + entry['case_id'] + ' --kind ' + kind,
                             'exit_code': 0,
                             'log': str(log_path.relative_to(HERE)), 'log_sha256': sha(log_path),
                             'result': str(result_path.relative_to(HERE)),
                             'result_sha256': sha(result_path)})
        life = lifecycle(EVENTS, 0)
        for events, code in ((EVENTS[::-1], 0), (EVENTS, 1)):
            try:
                lifecycle(events, code)
            except ValueError:
                pass
            else:
                raise ValueError('Invalid lifecycle accepted')
        life_log = folder / 'lifecycle.log'
        life_log.write_text(json.dumps({'case_id': entry['case_id'],
                                       'events': life['events'],
                                       'synthetic_only': True}) + '\n')
        life['log'] = str(life_log.relative_to(HERE))
        life['log_sha256'] = sha(life_log)
        proof = {'format': 'c229597-physical-sweep-cpu-fixtures-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures, 'lifecycle': life,
                 'sweep_target_realization_verified': False,
                 'native_executed': False, 'legal_verdict_claimed': False}
        proof_path = folder / 'proof.json'
        write(proof_path, proof)
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(HERE)),
                                         'sha256': sha(proof_path)}
    write(manifest_path, manifest)
    print(json.dumps({'physical_sweep_cases': 6, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
