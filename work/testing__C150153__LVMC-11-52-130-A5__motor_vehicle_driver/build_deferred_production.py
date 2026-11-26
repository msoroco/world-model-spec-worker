"""Select exact constructions that require original reviewed sources at capture."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from build_source_bound_bundles import MODULES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'execution-manifest.fallback-diagnostic.json'
TARGET = HERE / 'execution-manifest.json'
SOURCE_CHECK = """if hashlib.sha256(Path(packet).read_bytes()).hexdigest() != SITE_SHA256:
        raise ValueError('reviewed original site packet changed')
    verify(Path(packet), Path(source_root))"""
DEFERRED_CHECK = """_verified_original(Path(packet), Path(source_root))"""
VERIFY_FUNCTION = """def _verified_original(packet, source_root):
    reviewed = verify(packet, source_root)
    provenance = reviewed.get('source_provenance')
    if (not isinstance(provenance, dict) or
            provenance.get('kind') != 'original_reviewed_site' or
            provenance.get('diagnostic_fixture') is not False or
            not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('external original reviewed site provenance required')
    return reviewed

"""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deferred_construction(path: Path) -> dict:
    construction = json.loads(path.read_text())
    files = {item['path']: item for item in construction['files']}
    runner = files['runner.py']['content']
    runner, count = re.subn(r'^SITE_SHA256 = [^\n]+$', 'SITE_SHA256 = None', runner, count=1, flags=re.MULTILINE)
    if count != 1 or runner.count(SOURCE_CHECK) != 2:
        raise ValueError('source-bound runner site hash shape changed')
    runner = runner.replace(SOURCE_CHECK, DEFERRED_CHECK)
    runner = runner.replace('def run(adapter, packet, source_root, output):',
                            VERIFY_FUNCTION + 'def run(adapter, packet, source_root, output):', 1)
    old_scene = "if scene.get('reviewed_site_packet_sha256') != SITE_SHA256:\n        raise ValueError('reviewed site packet binding differs')"
    new_scene = "if scene.get('source_status') != 'original_reviewed_site_required_at_capture':\n        raise ValueError('original reviewed site capture requirement missing')"
    if runner.count(old_scene) != 1:
        raise ValueError('source-bound scene check shape changed')
    runner = runner.replace(old_scene, new_scene)
    files['runner.py']['content'] = runner
    scene = json.loads(files['scene.json']['content'])
    scene.pop('reviewed_site_packet_sha256')
    scene.pop('commanded_body_interval_m')
    scene['source_status'] = 'original_reviewed_site_required_at_capture'
    files['scene.json']['content'] = json.dumps(scene, indent=2) + '\n'
    for module in MODULES:
        files[module]['content'] = (HERE / module).read_text()
    construction['source_kind'] = 'original_reviewed_site_deferred'
    construction['static_checks'] = ['original reviewed source gate before capture',
                                     '20 Hz and 900 frames']
    return construction


def build() -> dict:
    if TARGET.exists():
        raise ValueError('refusing to overwrite selected production manifest')
    diagnostic = json.loads(SOURCE.read_text())
    if (diagnostic.get('status') !=
            'synthetic_fallback_diagnostic_only_unselected_original_capture_pending'):
        raise ValueError('expected unselected fallback diagnostic source')
    entries = []
    staged = []
    for old in diagnostic['cases']:
        case_id = old['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        entry = {key: value for key, value in old.items()
                 if key not in ('compatibility', 'offline', 'negative', 'diagnostic_only')}
        entry['source_selection_status'] = 'original_reviewed_site_required_at_capture'
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        for candidate_id in ('primary', 'fallback1'):
            candidate = entry if candidate_id == 'primary' else entry['candidates'][0]
            old_candidate = old if candidate_id == 'primary' else old['candidates'][0]
            construction = deferred_construction(HERE / old_candidate['construction'])
            target = HERE / 'cases' / kind / ('construction.deferred.' + candidate_id + '.json')
            if target.exists():
                raise ValueError('refusing to overwrite deferred construction: ' + kind)
            raw = (json.dumps(construction, indent=2, sort_keys=True) + '\n').encode()
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('deferred construction exceeds returned-file limit')
            staged.append((target, raw))
            candidate['construction'] = str(target.relative_to(HERE))
            candidate['construction_sha256'] = hashlib.sha256(raw).hexdigest()
            candidate.pop('compatibility', None)
            candidate.pop('offline', None)
            if candidate_id == 'primary':
                candidate.pop('negative', None)
        entries.append(entry)
        print(kind, 'source-deferred primary and fallback1 staged', flush=True)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': HERE.name,
                'status': 'original_reviewed_site_required_at_capture',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    for path, raw in staged:
        path.write_bytes(raw)
    TARGET.write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    build()
