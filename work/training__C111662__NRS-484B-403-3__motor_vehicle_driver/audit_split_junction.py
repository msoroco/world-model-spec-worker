"""Audit the isolated directional junction connector CPU probe."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'split-junction-experiment'
RUN = ROOT / '.runtime-work/c111662-split-junction'
MANIFEST = HERE / 'split-junction-experiment-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    manifest = read(MANIFEST)
    entry = manifest['cases'][0]
    construction_path = HERE / entry['construction']
    construction = read(construction_path)
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    require(manifest['runtime_manifest_sha256'] == runtime_sha, 'Probe binds another runtime')
    require(entry['construction_sha256'] == sha(construction_path), 'Construction binding changed')
    recipe_path = ROOT / entry['fixture_recipe']
    recipe = read(recipe_path)
    require(recipe['generator']['sha256'] == sha(ROOT / recipe['generator']['source']),
            'Fixture generator changed')
    road = next(item['content'] for item in construction['files'] if item['path'] == 'road.xodr')
    roads = {int(r.attrib['id']): r for r in ET.fromstring(road).findall('road')}
    require(set(roads) == {403, 404, 405, 406, 407, 408, 409, 410},
            'Directional junction roads differ')
    for ident in (404, 407):
        section = roads[ident].find('./lanes/laneSection')
        require(len(section.findall('./left/lane')) == 0 and
                len(section.findall('./right/lane')) == 3, 'Forward connector changed')
    for ident in (409, 410):
        section = roads[ident].find('./lanes/laneSection')
        require(len(section.findall('./left/lane')) == 3 and
                len(section.findall('./right/lane')) == 0, 'Reverse connector changed')
    require(read(RUN / 'offline-final2.log')['offline_passed'] is True,
            'Exact offline failed')
    compatibility = read(RUN / 'compatibility/compatibility.json')
    require(compatibility['passed'] is True and compatibility['negative_removed'] == 'raw.json',
            'Positive or missing-source compatibility failed')
    require(compatibility['runtime_manifest_sha256'] == runtime_sha and
            compatibility['construction_sha256'] == sha(construction_path) and
            compatibility['fixture_recipe_sha256'] == sha(recipe_path),
            'Compatibility is not bound to this source and recipe')
    report = read(RUN / 'compatibility/converted/adapter_report.json')
    coverage = report['occupancy_coverage']
    incomplete = [row['frame'] for row in coverage if row['incomplete_tracks'] or
                  any(not track['complete'] for track in row['tracks'])]
    require(report['frames'] == len(coverage) == 800 and not incomplete and
            report['occupancy_complete'] is True and
            report['atom_coverage']['atoms']['rel.occupies']['passed'] is True,
            'Mandatory occupancy coverage incomplete')
    centre = [row for row in report['native_centre_lines'] if row['road_id'] in (404, 407, 409, 410)]
    require(not centre, 'Generated divider crosses split junction')
    saved = read(RUN / 'saved/v0001/processing.json')
    require(saved['passed'] is True and saved['recorded_only'] is True and
            saved['originals_preserved'] is True and saved['missing_evidence'] is False and
            saved['timestamp_joins'] == {'frames': 800, 'passed': True,
                                         'missing_original_trace_or_map': False} and
            saved['physical_acceptance_claimed'] is False and
            saved['legal_acceptance_claimed'] is False,
            'Recorded-only saved proof incomplete or overclaims acceptance')
    for name, source in [('pinned-offline.log', 'offline-final2.log'),
                         ('pinned-compat.log', 'compatibility.log'),
                         ('pinned-saved.log', 'saved.log')]:
        (WORK / name).write_bytes((RUN / source).read_bytes())
    proof = {
        'format': 'c111662-split-junction-current-runtime-probe-v1',
        'status': 'isolated_diagnostic_only',
        'case_id': entry['case_id'],
        'candidate_id': 'primary',
        'runtime_manifest_sha256': runtime_sha,
        'manifest_sha256': sha(MANIFEST),
        'construction_sha256': sha(construction_path),
        'fixture_recipe_sha256': sha(recipe_path),
        'road_sha256': hashlib.sha256(road.encode()).hexdigest(),
        'offline_log_sha256': sha(WORK / 'pinned-offline.log'),
        'compatibility_log_sha256': sha(WORK / 'pinned-compat.log'),
        'saved_log_sha256': sha(WORK / 'pinned-saved.log'),
        'compatibility_receipt_sha256': sha(RUN / 'compatibility/compatibility.json'),
        'saved_receipt_sha256': sha(RUN / 'saved/v0001/processing.json'),
        'positive_compatibility_passed': True,
        'missing_raw_negative_rejected': True,
        'saved_processing_passed': True,
        'mandatory_occupancy_frames_complete': len(coverage),
        'incomplete_occupancy_frames': incomplete,
        'original_native_observed': False,
        'physical_or_legal_acceptance_claimed': False,
        'fidelity_gap': 'Directional connector topology is synthetic; source capture and same-map reference comparison remain unverified.',
    }
    path = WORK / 'current-proof.json'
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(path), 'occupancy_frames': len(coverage),
                      'selected_delivery_proved': False}))


if __name__ == '__main__':
    main()
