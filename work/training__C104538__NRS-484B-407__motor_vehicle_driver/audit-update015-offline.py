"""Independently audit current-runtime unselected exact construction receipts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof = json.loads((HERE / 'update015-offline-summary.json').read_text())
    assert manifest['runtime_manifest_sha256'] == proof['runtime_manifest_sha256'] == sha(REPO / 'runtime/pipeline/SOURCE-MANIFEST.json')
    assert proof['draft_manifest_sha256'] == sha(manifest_path)
    assert proof['selected'] is False and proof['simulation_started'] is False
    assert len(manifest['cases']) == 3 and len(proof['cases']) == 12
    seen = set()
    negatives = 0
    for case in manifest['cases']:
        suffix = case['case_id'].rsplit('__', 1)[1]
        candidates = [{'id': 'primary', 'construction': case['construction'],
                       'construction_sha256': case['construction_sha256']}] + case['candidates']
        assert [item['id'] for item in candidates] == ['primary', 'fallback1', 'fallback2', 'fallback3']
        assert len({item['construction_sha256'] for item in candidates}) == 4
        for item in candidates:
            candidate = item['id']
            key = (case['case_id'], candidate)
            assert key not in seen
            seen.add(key)
            assert sha(HERE / item['construction']) == item['construction_sha256']
            construction = json.loads((HERE / item['construction']).read_text())
            files = {entry['path']: entry['content'] for entry in construction['files']}
            config = json.loads(files['config.json'])
            assert construction['case_id'] == config['case_id'] == case['case_id']
            assert config['candidate_id'] == candidate
            for name in ('authored_road.xodr', 'obstruction.json', 'measurement.json'):
                assert files[name] == (HERE / 'draft-sightline' / suffix / ('road.xodr' if name == 'authored_road.xodr' else name)).read_text()
            row = next(row for row in proof['cases'] if (row['case_id'], row['candidate_id']) == key)
            assert row['exit_code'] == 0 and row['log_sha256'] == sha(HERE / row['log'])
            assert '"offline_passed": true' in (HERE / row['log']).read_text().lower()
            output = REPO / proof['output_root'] / suffix / candidate
            assert output.is_dir() and 'OK' in (output / 'offline.log').read_text()
            for name, content, expected in (
                ('authored_road.xodr', 'damaged road', 'Materialized authored road differs'),
                ('obstruction.json', '{}', 'Materialized obstruction differs')):
                if candidate != 'primary':
                    continue
                with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as temp:
                    target = Path(temp) / 'package'
                    shutil.copytree(output, target)
                    (target / name).write_text(content)
                    result = subprocess.run([sys.executable, str(target / 'runner.py'), '--check'],
                                            cwd=target, capture_output=True, text=True)
                    assert result.returncode != 0 and expected in result.stderr
                    negatives += 1
    assert len(seen) == 12
    return {'current_runtime_exact_offline_passed': len(seen),
            'damaged_source_rejections': negatives, 'selected': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
