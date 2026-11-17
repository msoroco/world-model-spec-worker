"""Show the independent mail draft audit rejects changed fixed conditions."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('mail_audit', ROOT / 'audit-mail-adjacent-draft.py')
AUDIT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AUDIT)


def rejected(label, **overrides):
    try:
        AUDIT.check(**overrides)
    except ValueError:
        return label
    raise AssertionError('Mail audit accepted mutation: ' + label)


def prove():
    manifest = json.loads((ROOT / 'execution-manifest-diagnostic-mail-adjacent-deposit-draft.json').read_text())
    saved = json.loads((ROOT / 'update042-mail-adjacent-saved-matrix.json').read_text())
    package = json.loads((ROOT / 'selected-primary/mail_adjacent_deposit/construction.json').read_text())
    config = json.loads(next(row['content'] for row in package['files'] if row['path']=='config.json'))
    tests = []
    altered = copy.deepcopy(manifest)
    altered['cases'][0]['candidates'][0]['construction_sha256'] = '0'*64
    tests.append(rejected('fallback construction hash',manifest=altered))
    altered = copy.deepcopy(saved)
    altered['candidates'][1]['frames'] = 360
    tests.append(rejected('saved frame count',saved=altered))
    altered = copy.deepcopy(config)
    altered['activity_request'] = None
    tests.append(rejected('mail activity removed',configurations={'primary':altered}))
    altered = copy.deepcopy(config)
    altered['native_blueprint'] = 'vehicle.carlamotors.firetruck'
    tests.append(rejected('ordinary body changed',configurations={'primary':altered}))
    return {'rejected_mutations':tests,'all_rejected':True}


if __name__=='__main__':
    print(json.dumps(prove(),indent=2))
