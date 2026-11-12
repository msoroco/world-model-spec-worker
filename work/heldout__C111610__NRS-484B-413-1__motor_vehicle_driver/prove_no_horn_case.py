"""Run exact offline and positive/negative compatibility for the no-horn pair."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = ROOT.parent / 'heldout__C111603__NRS-484B-413-1__motor_vehicle_driver'
PY = str(REPO / '.venv-cpu/bin/python')
CASE = ROOT.name + '__pedestrian_no_horn_before_turn'
SOURCE_CASE = SOURCE.name + '__ped_no_horn_audio'
MANIFEST = ROOT / 'execution-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)


def save():
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


manifest = json.loads(MANIFEST.read_text())
entry = next(c for c in manifest['cases'] if c['case_id'] == CASE)
source_manifest = json.loads((SOURCE / 'execution-manifest.json').read_text())
source_entry = next(c for c in source_manifest['cases'] if c['case_id'] == SOURCE_CASE)
for candidate_id in ['primary', 'fallback1', 'fallback2', 'fallback3']:
    if candidate_id != 'primary':
        source_candidate = next(c for c in source_entry['candidates'] if c['id'] == candidate_id)
        construction = 'pedestrian-no-horn-' + candidate_id + '-construction.json'
        data = (SOURCE / source_candidate['construction']).read_text().replace(SOURCE_CASE, CASE).replace(SOURCE.name, ROOT.name).replace('C111603', 'C111610')
        (ROOT / construction).write_text(data)
        candidate = {k: source_candidate[k] for k in ['id', 'trigger', 'changed_knobs']}
        candidate.update(construction=construction, construction_sha256=digest(ROOT / construction))
        entry['candidates'] = [c for c in entry['candidates'] if c['id'] != candidate_id] + [candidate]
        save()
    else:
        candidate = entry
    prefix = 'pedestrian-no-horn-' + candidate_id
    base = [PY, 'runtime.py']
    offline = base + ['offline', '--manifest', str(MANIFEST.relative_to(REPO)), '--case', CASE,
                      '--candidate', candidate_id, '--output', '.runtime-work/c111610-no-horn-' + candidate_id + '-offline-proof', '--python', PY]
    offline_log = ROOT / (prefix + '-offline.log')
    run(offline, offline_log)
    candidate['offline'] = {'command': ' '.join(offline), 'exit_code': 0, 'log': offline_log.name,
                            'log_sha256': digest(offline_log), 'construction_sha256': candidate['construction_sha256']}
    save()
    output = REPO / ('.runtime-work/c111610-no-horn-' + candidate_id + '-compat-proof')
    compatibility = base + ['compatibility', '--manifest', str(MANIFEST.relative_to(REPO)), '--case', CASE,
                            '--candidate', candidate_id, '--output', str(output.relative_to(REPO)),
                            '--library', 'runtime/library', '--validator', '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    run(compatibility, ROOT / (prefix + '-compatibility.log'))
    receipt = ROOT / (prefix + '-receipt.json')
    analysis = ROOT / (prefix + '-analysis.log')
    negative = ROOT / (prefix + '-negative.log')
    for source_name, target in [('compatibility.json', receipt), ('compatibility-analysis.log', analysis), ('negative-analysis.log', negative)]:
        shutil.copy2(output / source_name, target)
    assert json.loads(receipt.read_text())['passed']
    candidate['compatibility'] = {'receipt': receipt.name, 'sha256': digest(receipt), 'log': analysis.name, 'negative_log': negative.name}
    if candidate_id == 'primary':
        candidate['negative'] = {'log': negative.name}
    save()
    print(candidate_id, 'offline and positive/negative compatibility passed', flush=True)
