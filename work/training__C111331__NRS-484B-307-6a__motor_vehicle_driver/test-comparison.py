"""Exercise independent comparison rejection of changed fixed motion policy."""
import json
import shutil
import tempfile
from pathlib import Path

from comparison_audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
reference = ROOT / '.runtime-work/c111331-update043b-reference-primary-compat'
contrast = ROOT / '.runtime-work/c111331-update043b-contrast-primary-compat'
positive = audit(reference, contrast, diagnostic=True)
assert positive['passed'] and positive['entry_frame'] == 203
with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c111331-comparison-negative-') as temp:
    altered = Path(temp)
    for name in ('analysis-report.json', 'config.json', 'native-requests.jsonl'):
        shutil.copyfile(contrast / name, altered / name)
    config = json.loads((altered / 'config.json').read_text())
    config['knobs']['speed_m_per_frame'] += .01
    (altered / 'config.json').write_text(json.dumps(config))
    try:
        audit(reference, altered, diagnostic=True)
    except ValueError as exc:
        assert 'Fixed vehicle motion policy differs' in str(exc), str(exc)
    else:
        raise AssertionError('Changed fixed motion policy accepted')
print('comparison positive and fixed-condition negative passed')
