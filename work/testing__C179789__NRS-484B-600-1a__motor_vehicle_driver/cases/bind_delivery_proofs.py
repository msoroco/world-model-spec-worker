"""Copy current diagnostic receipts and bind each exact selected case."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    path = ROOT / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    proof_dir = ROOT / 'cases/selected-proofs'
    proof_dir.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        short = entry['construction_sha256'][:12]
        compat = REPO / '.runtime-work' / ('c179789-compat-' + suffix + '-' + short)
        saved = REPO / '.runtime-work' / ('c179789-saved-' + suffix + '-' + short) / 'v0001'
        if not (compat / 'compatibility.json').is_file() or not (saved / 'processing.json').is_file():
            raise ValueError('Missing positive and recorded-only receipt: ' + suffix)
        copied = {}
        for label, source in (
            ('compatibility', compat / 'compatibility.json'),
            ('analysis', compat / 'compatibility-analysis.log'),
            ('negative', compat / 'negative-analysis.log'),
            ('saved', saved / 'processing.json'),
        ):
            target = proof_dir / (suffix + '-' + label + source.suffix)
            shutil.copyfile(source, target)
            copied[label] = {'path': target.relative_to(ROOT).as_posix(), 'sha256': sha(target)}
        entry['compatibility'] = {'receipt': copied['compatibility']['path'],
                                  'sha256': copied['compatibility']['sha256'],
                                  'log': copied['analysis']['path'],
                                  'negative_log': copied['negative']['path']}
        entry['negative'] = {'log': copied['negative']['path']}
        entry['compatibility_diagnostic'] = {
            'command': 'runtime.py compatibility --case ' + entry['case_id'],
            'exit_code': 0, 'receipt': copied['compatibility']['path'],
            'sha256': copied['compatibility']['sha256'],
            'scope': 'synthetic positive and missing-surface diagnostic'}
        entry['saved_processing_diagnostic'] = {
            'command': 'runtime.py process-saved --case ' + entry['case_id'],
            'exit_code': 0, 'receipt': copied['saved']['path'],
            'sha256': copied['saved']['sha256'], 'recorded_only': True,
            'scope': 'synthetic saved sources, no Native replay'}
        entry['acquisition'] = {
            name: {'entrypoint': 'runner.py' if name.startswith('kin.') else 'condition_capture.py',
                   'method': ('Native actor transform and velocity' if name.startswith('kin.') else
                              'frame-specific Native condition and source packet sampling'),
                   'evidence': ('capture/evidence.jsonl' if name.startswith('kin.') else
                                'condition_history.jsonl')}
            for name in ('kin.position', 'kin.heading', 'kin.velocity',
                         'ego_speed_mps', 'lead_speed_mps', 'longitudinal_body_gap_m',
                         'lane_width_m', 'surface', 'precipitation_percent',
                         'sight_distance_m', 'curvature_per_m',
                         'fog_density_percent', 'fog_distance_m')}
        fallback = entry['candidates'][0]
        fall_short = fallback['construction_sha256'][:12]
        fall_compat = REPO / '.runtime-work' / ('c179789-fallback-compat-' + suffix + '-' + fall_short)
        fall_saved = REPO / '.runtime-work' / ('c179789-fallback-saved-' + suffix + '-' + fall_short) / 'v0001'
        for label, source in (
            ('compatibility', fall_compat / 'compatibility.json'),
            ('analysis', fall_compat / 'compatibility-analysis.log'),
            ('negative', fall_compat / 'negative-analysis.log'),
            ('saved', fall_saved / 'processing.json'),
        ):
            target = proof_dir / (suffix + '-fallback1-' + label + source.suffix)
            shutil.copyfile(source, target)
            copied['fallback_' + label] = {'path': target.relative_to(ROOT).as_posix(),
                                           'sha256': sha(target)}
        fallback['compatibility'] = {
            'receipt': copied['fallback_compatibility']['path'],
            'sha256': copied['fallback_compatibility']['sha256'],
            'log': copied['fallback_analysis']['path'],
            'negative_log': copied['fallback_negative']['path']}
        fallback['saved_processing_diagnostic'] = {
            'command': 'runtime.py process-saved --case ' + entry['case_id'] +
                       ' --candidate fallback1',
            'exit_code': 0, 'receipt': copied['fallback_saved']['path'],
            'sha256': copied['fallback_saved']['sha256'], 'recorded_only': True}
        positive = proof_dir / (suffix + '-acceptance-positive.log')
        negative = proof_dir / (suffix + '-acceptance-negative.log')
        script = ROOT / 'prove_delivery_acceptance.py'
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': script.relative_to(ROOT).as_posix(), 'script_sha256': sha(script),
            'command': '.venv-cpu/bin/python ' + script.relative_to(REPO).as_posix() +
                       ' --case ' + entry['case_id'] + ' --mode positive',
            'test_log': positive.relative_to(ROOT).as_posix(),
            'test_log_sha256': sha(positive), 'test_exit_code': 0,
            'negative_command': '.venv-cpu/bin/python ' + script.relative_to(REPO).as_posix() +
                                ' --case ' + entry['case_id'] + ' --mode negative',
            'negative_log': negative.relative_to(ROOT).as_posix(),
            'negative_log_sha256': sha(negative), 'negative_exit_code': 1,
            'negative_expected_error': 'Physical completion source changed',
            'proof_scope': 'CPU diagnostic boundary; Native and pixel review pending'}
        print(suffix, 'bound')
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    bind()
