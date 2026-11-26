"""Check the selected electric-bicycle contrast on saved-only analyses."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records = {}
    for suffix, tag in (('electric_bicycle_pass_wide', 'ebike-wide'),
                        ('electric_bicycle_pass_narrow', 'ebike-narrow')):
        path = ROOT / 'draft-ebike' / suffix / 'primary/construction.json'
        construction = json.loads(path.read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        stage = REPO / '.runtime-work' / ('c146108-saved-final3-' + tag) / 'v0001'
        report_path = stage / 'analysis/analysis-report.json'
        processing_path = stage / 'processing.json'
        report = json.loads(report_path.read_text())
        processing = json.loads(processing_path.read_text())
        assert processing['passed'] and processing['recorded_only']
        assert processing['native_revision']['construction_sha256'] == sha(path)
        measurement = report['measurements']['full_pass']['value']
        assert measurement['frames'] == 600 and not measurement['legal_verdict_claimed']
        records[suffix] = {'case_id': construction['case_id'], 'construction_sha256': sha(path),
            'runner_sha256': hashlib.sha256(files['runner.py'].encode()).hexdigest(),
            'road_sha256': hashlib.sha256(files['geometry_ebike.py'].encode()).hexdigest(),
            'rider_y_m': config['rider_y_m'], 'pass_start_frame': measurement['pass_start_frame'],
            'pass_clear_frame': measurement['pass_clear_frame'],
            'minimum_surface_gap_m': measurement['minimum_surface_gap_m'],
            'original_source_sha256': measurement['source_sha256'],
            'analysis_report_sha256': sha(report_path), 'processing_sha256': sha(processing_path)}
    wide = records['electric_bicycle_pass_wide']
    narrow = records['electric_bicycle_pass_narrow']
    assert wide['runner_sha256'] == narrow['runner_sha256']
    assert wide['road_sha256'] == narrow['road_sha256']
    assert wide['pass_start_frame'] == narrow['pass_start_frame']
    assert wide['pass_clear_frame'] == narrow['pass_clear_frame']
    assert wide['rider_y_m'] != narrow['rider_y_m']
    assert 0 < narrow['minimum_surface_gap_m'] < wide['minimum_surface_gap_m']
    proof = {'format': 'c146108-saved-comparison-v1', 'passed': True,
        'controlled_variable': 'rider lateral center and resulting full-body surface gap',
        'records': records, 'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
        'limitation': 'Both acquisitions are synthetic CPU fixtures; no Native camera visibility or statutory endangerment finding'}
    path = ROOT / 'saved-comparison-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'sha256': sha(path),
                      'wide_gap_m': wide['minimum_surface_gap_m'],
                      'narrow_gap_m': narrow['minimum_surface_gap_m']}, sort_keys=True))


if __name__ == '__main__':
    main()
