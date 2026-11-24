"""Independently audit the first current camera-risk fallback CPU path."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def frames(path):
    completed = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, check=True, timeout=120)
    return int(completed.stdout.strip())


def main():
    manifest = read(HERE / 'current-diagnostic-manifest.json')
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith('condition_b'))
    fallback = next(item for item in entry['candidates'] if item['id'] == 'fallback3')
    primary_path = HERE / entry['construction']
    construction_path = HERE / fallback['construction']
    primary = read(primary_path)
    construction = read(construction_path)
    assert entry['construction_sha256'] == sha(primary_path)
    assert fallback['construction_sha256'] == sha(construction_path)
    assert primary['case_id'] == construction['case_id'] == entry['case_id']
    def files(bundle):
        return {item['path']: item['content'] for item in bundle['files']}
    pf, ff = files(primary), files(construction)
    assert pf['finalize.py'] == ff['finalize.py']
    assert pf['measure_following.py'] == ff['measure_following.py']
    assert pf['geometry.py'] == ff['geometry.py']
    assert pf['runner.py'] == ff['runner.py']
    pconfig, fconfig = json.loads(pf['config.json']), json.loads(ff['config.json'])
    assert {key for key in pconfig if pconfig[key] != fconfig[key]} == {'candidate_id'}
    assert pconfig['candidate_id'] == 'primary' and fconfig['candidate_id'] == 'fallback3'
    compat = ROOT / '.runtime-work/c102304-current-compat-b-fallback3'
    saved = ROOT / '.runtime-work/c102304-current-saved-b-fallback3/v0001'
    c, s = read(compat / 'compatibility.json'), read(saved / 'processing.json')
    assert c['passed'] is True and c['case_id'] == entry['case_id']
    assert c['candidate_id'] == 'fallback3'
    assert c['construction_sha256'] == sha(construction_path)
    assert c['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    recipe = ROOT / fallback['fixture_recipe']
    assert c['fixture_recipe_sha256'] == sha(recipe)
    assert c['negative_removed'] == 'native_samples.jsonl'
    assert c['negative_error_contains'] in (compat / 'negative-analysis.log').read_text()
    assert c['negative_log_sha256'] == sha(compat / 'negative-analysis.log')
    assert s['passed'] is True and s['recorded_only'] is True
    assert s['case_id'] == entry['case_id'] and s['candidate_id'] == 'fallback3'
    assert s['analysis_revision']['construction_sha256'] == sha(construction_path)
    assert s['timestamp_joins']['passed'] is True and s['timestamp_joins']['frames'] == 900
    assert s['final_video_checks']['passed'] is True and s['final_video_checks']['frames'] == 900
    assert s['originals_preserved'] is True
    assert s['physical_acceptance_claimed'] is False and s['legal_acceptance_claimed'] is False
    report = read(compat / 'analysis-report.json')
    measurement = report['measurements']['moving_following_interval']['value']
    assert measurement['median_bumper_gap_m'] == 25.0
    videos = {name: frames(compat / (name + '.mkv')) for name in
              ('overview', 'approach', 'reference_corner', 'driver_reference')}
    assert set(videos.values()) == {900}
    result = {
        'format': 'c102304-current-fallback3-independent-audit-v1',
        'passed': True, 'case_id': entry['case_id'], 'candidate_id': 'fallback3',
        'construction_sha256': sha(construction_path), 'recipe_sha256': sha(recipe),
        'compatibility_sha256': sha(compat / 'compatibility.json'),
        'process_saved_sha256': sha(saved / 'processing.json'),
        'camera_frames': videos, 'median_bumper_gap_m': 25.0,
        'missing_source_rejected': True,
        'fixture_reuses_primary_synthetic_frames': True,
        'physical_camera_framing_proven': False,
        'legal_outcome_claimed': False,
    }
    (HERE / 'current-fallback3-b-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'camera_frames': videos,
                      'physical_camera_framing_proven': False}))


if __name__ == '__main__':
    main()
