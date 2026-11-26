"""Exercise the independent comparison on source-shaped CPU diagnostics."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import TARGETS, audit


def main():
    dirs = [ROOT/'native/diagnostic'/probe/'sources' for probe in TARGETS]
    configs = [ROOT/'cases'/probe/'primary/config.json' for probe in TARGETS]
    positive = audit(dirs, configs)
    if len(positive['cases']) != 3 or positive['physical_acceptance_claimed']:
        raise ValueError('Positive comparison diagnostic incomplete')
    output = ROOT/'selected-proofs'/'comparison'
    output.mkdir(parents=True, exist_ok=True)
    (output/'positive.json').write_text(json.dumps(positive,indent=2)+'\n')
    (output/'positive.log').write_text('PASS three source-bound lane-change speed cases and fixed road/camera frame joins\n')
    with tempfile.TemporaryDirectory(dir=Path('.runtime-work').resolve(),prefix='c245490-comparison-') as temporary:
        missing = Path(temporary)
        for p in dirs[1].iterdir():
            if p.name == 'speed-lane-history.jsonl':
                continue
            if p.is_dir():
                shutil.copytree(p,missing/p.name)
            else:
                shutil.copyfile(p,missing/p.name)
        try:
            audit([dirs[0],missing,dirs[2]],configs)
        except ValueError as error:
            if 'Missing original comparison source: speed-lane-history.jsonl' not in str(error):
                raise
            (output/'negative.log').write_text('PASS rejected '+str(error)+'\n')
        else:
            raise ValueError('Missing original comparison history was accepted')


if __name__ == '__main__':
    main()
