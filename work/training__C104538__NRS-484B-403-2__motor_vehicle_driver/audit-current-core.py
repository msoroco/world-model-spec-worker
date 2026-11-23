"""Independent audit of all unselected 600-frame current JSON graph probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check():
    records = []
    for suffix in ('witness_1', 'witness_2'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            log = HERE / f'current-core-{suffix}-{candidate}.log'
            receipt = json.loads(log.read_text())
            attempt = Path(receipt['scratch']) / 'attempt'
            if receipt['case'] != suffix or receipt['candidate'] != candidate:
                raise ValueError('Current Core case/candidate receipt differs')
            if not receipt['core']['converted'] or not receipt['core']['decoder_checked'] or not receipt['final_decode_passed'] or receipt['render_frames'] != 600:
                raise ValueError('Current Core/Lean/render/final decode incomplete')
            config = json.loads((attempt / 'config.json').read_text())
            if (config['case_suffix'], config['candidate_id'], config['duration_s'], config['rate_hz']) != (suffix, candidate, 30, 20):
                raise ValueError('Exact 30-second construction identity differs')
            sources = (rows(attempt / 'native_samples.jsonl'),
                       rows(attempt / 'capture/native/frames.jsonl'),
                       rows(attempt / 'capture/evidence.jsonl'))
            if any(len(source) != 600 for source in sources):
                raise ValueError('Current Core source frame inventory incomplete')
            for sample, frame, evidence in zip(*sources):
                if sample['native_frame'] != frame['frame'] or evidence['original_frame'] != frame['frame']:
                    raise ValueError('Current Core source frame join differs')
                if evidence['ego']['speed_provenance'] != 'synthetic_native_sample':
                    raise ValueError('Diagnostic speed mislabeled as original')
                graph_path = attempt / 'capture/native' / frame['adapter_graph']
                graph = json.loads(graph_path.read_text())
                if graph['format'] != 'native-adapter-graph-v1' or graph['metadata']['frame'] != frame['frame']:
                    raise ValueError('Current Core JSON graph differs from source frame')
            result = json.loads((attempt / 'result.json').read_text())
            measured = json.loads((attempt / 'analysis-report.json').read_text())['measurements']['signed_u_turn']['value']
            if result['accepted'] or result['legal_verdict_claimed'] or result['setup_confirmed'] or measured['u_turn_within_governed_region_observed'] != (suffix == 'witness_2'):
                raise ValueError('Current Core synthetic result claims physical success or wrong movement')
            records.append({'case': suffix, 'candidate': candidate, 'frames': 600,
                            'log_sha256': sha(log), 'source_sha256': sha(attempt / 'native_samples.jsonl'),
                            'analysis_sha256': sha(attempt / 'analysis-report.json'),
                            'final_decode_sha256': sha(attempt / 'final-decode.json'),
                            'u_turn_observed': measured['u_turn_within_governed_region_observed']})
    if len(records) != 8:
        raise ValueError('Current Core candidate inventory incomplete')
    return {'format': 'c104538-current-core-diagnostic-audit-v1',
            'passed': True, 'candidate_receipts': records,
            'native_executed': False, 'original_sign_pixels_reviewed': False,
            'selected': False, 'accepted': False}


if __name__ == '__main__':
    proof = check()
    path = HERE / 'current-core-audit.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'candidates': len(proof['candidate_receipts']),
                      'frames_per_candidate': 600, 'selected': False}))
