"""Copy exact CPU receipts into the portable partial assignment package."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = {'bicycle_pass_wide': 'bicycle',
         'electric_bicycle_pass_wide': 'ebike-wide',
         'electric_bicycle_pass_narrow': 'ebike-narrow'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {'path': str(target.relative_to(ROOT)), 'sha256': sha(target)}


def main():
    report = {'format': 'c146108-selected-cpu-evidence-v1', 'assignment_id': ROOT.name,
              'scope': 'synthetic diagnostic and saved-only software proof; Native physical and legal acceptance unclaimed',
              'cases': []}
    for suffix, tag in CASES.items():
        source = REPO / '.runtime-work' / ('c146108-public-' + suffix + '-physical')
        saved = REPO / '.runtime-work' / ('c146108-saved-' + tag) / 'v0001'
        target = ROOT / 'selected-proofs' / suffix
        files = {'compatibility': copy(source / 'compatibility.json', target / 'compatibility.json'),
                 'public_analysis_log': copy(source / 'compatibility-analysis.log', target / 'public-analysis.log'),
                 'negative_analysis_log': copy(source / 'negative-analysis.log', target / 'negative-analysis.log'),
                 'saved_processing': copy(saved / 'processing.json', target / 'processing.json'),
                 'saved_analysis_log': copy(saved / 'analysis.log', target / 'saved-analysis.log')}
        compatibility = json.loads((target / 'compatibility.json').read_text())
        processing = json.loads((target / 'processing.json').read_text())
        assert compatibility['passed'] and compatibility['case_id'] == ROOT.name + '__' + suffix
        assert processing['passed'] and processing['recorded_only'] and processing['originals_preserved']
        assert compatibility['construction_sha256'] == processing['native_revision']['construction_sha256']
        assert compatibility['log_sha256'] == files['public_analysis_log']['sha256']
        assert compatibility['negative_log_sha256'] == files['negative_analysis_log']['sha256']
        assert processing['analysis_log_sha256'] == files['saved_analysis_log']['sha256']
        report['cases'].append({'case_id': compatibility['case_id'],
            'construction_sha256': compatibility['construction_sha256'], 'files': files,
            'public_compatibility_passed': True, 'saved_only_passed': True,
            'physical_preparation': str((Path('selected-physical') / suffix / 'physical-preparation.json')),
            'physical_preparation_sha256': sha(ROOT / 'selected-physical' / suffix / 'physical-preparation.json')})
    path = ROOT / 'selected-evidence.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(report['cases']), 'sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
