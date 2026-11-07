"""Exact CPU compatibility preflight; full Core/video receipt remains pending."""
import copy
import hashlib
import json
from pathlib import Path
import sys

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import select
from worker_exchange.package_compatibility import check_source_packets
from worker_exchange.atom_preflight import check_required_atoms


def prove():
    manifest_path = FOLDER / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    ontology = (ROOT / 'runtime/pipeline/library/TrafficSpec/Core/Vocab/Ontology/Ids.lean').read_text()
    results = []
    for entry in manifest['cases']:
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            _, selected, proposal = select(manifest_path, entry['case_id'], candidate)
            files = {item['path']: item['content'] for item in proposal['files']}
            config = json.loads(files['config.json'])
            check_source_packets(config, set(files))
            check_required_atoms(ROOT / 'runtime/pipeline', config['required_atoms'],
                                 config['source_packets'])
            assert config['case_id'] == entry['case_id']
            assert config['candidate_id'] == candidate
            assert all('"' + atom + '"' in ontology for atom in config['required_atoms'])
            assert set(config['case_specific_saved_observables']) == {
                'emergency_vehicle_authority', 'front_red_warning_lamp'}
            changed = copy.deepcopy(config)
            changed['source_packets'] = ['source-scope.json']
            try:
                check_source_packets(changed, set(files))
            except ValueError as error:
                assert 'Unknown source packet declaration' in str(error)
            else:
                raise AssertionError('Unsupported source packet was accepted')
            results.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'construction_sha256': selected['construction_sha256'],
                            'runtime_source_packet_positive': True,
                            'adapter_atom_path_positive': True,
                            'unsupported_source_packet_negative_rejected': True,
                            'ontology_ids_verified': True})
    assert len(results) == 8
    return {'passed': True,
            'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'results': results,
            'scope': 'exact selection, source-packet declaration and ontology preflight only; '
                     'no full portable Core/Lean/video compatibility receipt'}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
