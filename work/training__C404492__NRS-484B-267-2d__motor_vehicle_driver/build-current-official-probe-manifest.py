"""Bind selected regulatory draft sources for current-runtime CPU compatibility."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    draft = json.loads((HERE / 'draft-official-manifest.json').read_text())
    batch = json.loads((ROOT / 'batch.json').read_text())
    entries = []
    for source in draft['cases']:
        suffix = source['case_id'].rsplit('__', 1)[-1]
        entries.append({
            'case_id': source['case_id'], 'id': 'primary', 'kind': 'delivery',
            'construction': source['construction'],
            'construction_sha256': source['construction_sha256'],
            'measurement_contract': f'measurement-contracts/{suffix}.json',
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'source-bound-emergency-abreast-v1'},
            'candidate_risk': {'status': 'physical',
                               'reason': 'Regulatory authority, flashing equipment and original camera visibility need source review'},
            'candidates': source['candidates'],
            'fixture_recipe': (HERE / f'current-{suffix}-recipe.json').relative_to(ROOT).as_posix(),
        })
    target = HERE / 'current-official-probe-manifest.json'
    target.write_text(json.dumps({
        'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'status': 'partial', 'delivery_ready': False,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'cases': entries,
    }, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'manifest': target.name}))


if __name__ == '__main__':
    main()
