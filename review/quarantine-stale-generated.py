"""Move only the known obsolete untracked generated manifest out of frozen runtime."""
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
(root / '.runtime-work').mkdir(exist_ok=True)
paths = [
    'runtime/runs/scenario_pipeline/inputs/shared/manifest.json',
    'runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json',
]
for relative in paths:
    source = root / relative
    if not source.exists():
        continue
    if source.is_symlink() or not source.is_file():
        raise SystemExit('Unexpected generated path type: ' + relative)
    tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', relative],
                             cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if tracked.returncode == 0:
        raise SystemExit('Refusing to move tracked runtime file: ' + relative)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target_dir = Path(tempfile.mkdtemp(prefix='stale-runtime-', dir=root / '.runtime-work'))
    target = target_dir / 'manifest.json'
    shutil.move(source, target)
    (target_dir / 'receipt.json').write_text(json.dumps({
        'source': relative, 'destination': str(target.relative_to(root)),
        'sha256': digest, 'reason': 'obsolete generated diagnostic file outside ignored output root',
    }, indent=2) + '\n')
    print('Quarantined obsolete generated manifest:', relative)
