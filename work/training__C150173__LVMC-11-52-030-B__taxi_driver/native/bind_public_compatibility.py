"""Retain exact current-runtime public compatibility receipts for taxi cases."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c150173-owner'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((BASE / 'selected-draft-manifest.json').read_text())
    retained = []
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        for candidate in ('primary', 'fallback1'):
            version = 15 if suffix in ('probe_a', 'probe_c') else 16
            source = SCRATCH / f'selected-compatibility-{suffix}-{candidate}-v{version}'
            receipt = json.loads((source / 'compatibility.json').read_text())
            construction_sha = (entry['construction_sha256'] if candidate == 'primary'
                                else entry['candidates'][0]['construction_sha256'])
            if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                    receipt.get('candidate_id') != candidate or
                    receipt.get('construction_sha256') != construction_sha or
                    receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256'] or
                    receipt.get('log_sha256') != sha(source / 'compatibility-analysis.log') or
                    receipt.get('negative_log_sha256') != sha(source / 'negative-analysis.log') or
                    'negative_case_source' not in receipt.get('checks', [])):
                raise ValueError('Current taxi compatibility receipt differs: ' + suffix + candidate)
            destination = BASE / 'native-selected' / suffix
            paths = {}
            for filename in ('compatibility.json', 'compatibility-analysis.log',
                             'negative-analysis.log'):
                retained_name = candidate + '-' + filename
                target = destination / retained_name
                target.write_bytes((source / filename).read_bytes())
                paths[filename] = {'path': str(target.relative_to(BASE)),
                                   'sha256': sha(target)}
            retained.append({'case_id': case, 'candidate_id': candidate,
                             'construction_sha256': construction_sha,
                             'files': paths})
    output = BASE / 'native-selected' / 'public-compatibility-summary.json'
    output.write_text(json.dumps({'format': 'c150173-public-compatibility-v1',
                                  'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                                  'cases': retained}, indent=2) + '\n')
    print(json.dumps({'receipts': len(retained), 'summary_sha256': sha(output)}))


if __name__ == '__main__':
    main()
