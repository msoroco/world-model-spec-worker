"""Retain source-hashed text receipts for all signed red-curb candidates."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__ordinary_red_signed'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    out = ROOT / 'selected-ordinary_red_signed-current-receipts'
    out.mkdir(exist_ok=True)
    entries = {}
    for candidate in CANDIDATES:
        suffix = '' if candidate == 'primary' else '-' + candidate
        manifest = ROOT / ('execution-manifest-diagnostic-ordinary_red_signed' +
                           suffix + '.json')
        entry = next(row for row in json.loads(manifest.read_text())['cases']
                     if row['case_id'] == CASE)
        construction = (ROOT / 'selected-primary/ordinary_red_signed/construction.json'
                        if candidate == 'primary' else
                        ROOT / 'selected-fallbacks/ordinary_red_signed' /
                        candidate / 'construction.json')
        prefix = REPO / '.runtime-work' / (
            'C150142-u023d-signed-primary' if candidate == 'primary'
            else 'C150142-u023-signed-' + candidate)
        sources = {
            'compatibility': Path(str(prefix) + '-compat/compatibility.json'),
            'saved': Path(str(prefix) + '-saved/v0001/processing.json'),
            'result': Path(str(prefix) + '-saved/v0001/analysis/result.json'),
            'analysis': Path(str(prefix) + '-saved/v0001/analysis/analysis-report.json'),
            'offline_test': Path(str(prefix) + '-offline/offline.log'),
            'negative_analysis': Path(str(prefix) + '-compat/negative-analysis.log')}
        folder = out / candidate
        folder.mkdir(exist_ok=True)
        receipts = {}
        for name, source in sources.items():
            target = folder / (name + ('.log' if name.endswith('test') or
                                      name == 'negative_analysis' else '.json'))
            shutil.copyfile(source, target)
            receipts[name] = {'path': target.relative_to(ROOT).as_posix(),
                              'sha256': sha(target)}
        compat = json.loads((folder / 'compatibility.json').read_text())
        saved = json.loads((folder / 'saved.json').read_text())
        result = json.loads((folder / 'result.json').read_text())
        if not (compat['passed'] and saved['passed'] and saved['originals_preserved']
                and not saved['missing_evidence']
                and compat['construction_sha256'] == sha(construction)
                and saved['analysis_revision']['construction_sha256'] == sha(construction)):
            raise ValueError('Signed candidate proof incomplete: ' + candidate)
        log_prefix = 'update023-signed' + suffix
        logs = {stage: sha(ROOT / (log_prefix + '-' + stage + '.log'))
                for stage in ('offline', 'compat', 'prepare', 'saved')}
        entries[candidate] = {
            'manifest': manifest.relative_to(ROOT).as_posix(),
            'manifest_sha256': sha(manifest),
            'construction': construction.relative_to(ROOT).as_posix(),
            'construction_sha256': sha(construction),
            'fixture_recipe_sha256': sha(REPO / entry['fixture_recipe']),
            'logs': logs, 'receipts': receipts,
            'synthetic_red_stopped_frames':
                result['measured_values']['red_curb_stopped_frames']}
    index = {'format': 'c150142-signed-candidate-cpu-index-v1',
             'case_id': CASE, 'status': 'diagnostic_cpu_proven',
             'original_native_observed': False,
             'physical_acceptance_claimed': False,
             'candidate_count': 4, 'candidates': entries}
    path = out / 'proof-index.json'
    path.write_text(json.dumps(index, indent=2) + '\n')
    return {'case_id': CASE, 'index_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(bind(), sort_keys=True))
