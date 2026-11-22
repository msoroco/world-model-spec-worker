"""Audit the two-case isolated shared-map CPU construction."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'shared-junction-experiment'
RUN = ROOT / '.runtime-work/c111662-shared-junction'
MANIFEST = HERE / 'shared-junction-experiment-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = read(MANIFEST)
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    require(manifest['runtime_manifest_sha256'] == runtime_sha, 'Probe binds another runtime')
    require(len(manifest['cases']) == 2, 'Reference and contrast cases required')
    cases = {}
    roads = set()
    centers = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        require(suffix in ('reference', 'contrast') and suffix not in cases,
                'Duplicate or unexpected case')
        construction_path = HERE / entry['construction']
        construction = read(construction_path)
        construction_sha = sha(construction_path)
        require(entry['construction_sha256'] == construction_sha, 'Construction binding changed')
        road = next(item['content'] for item in construction['files'] if item['path'] == 'road.xodr')
        road_sha = hashlib.sha256(road.encode()).hexdigest()
        roads.add(road_sha)
        root = ET.fromstring(road)
        road_items = {int(item.attrib['id']): item for item in root.findall('road')}
        require(set(road_items) == {403, 404, 405, 406, 407, 408, 409, 410},
                'Directional road set changed')
        approach = road_items[403].find('lanes').findall('laneSection')
        require([section.attrib['s'] for section in approach] == ['0', '55', '67'] and
                all(lane.attrib['type'] == 'shoulder'
                    for lane in approach[1].findall('./left/lane')),
                'Approach opening changed')
        for ident, expected in ((404, (0, 3)), (407, (0, 3)),
                                (409, (3, 0)), (410, (3, 0))):
            section = road_items[ident].find('./lanes/laneSection')
            actual = (len(section.findall('./left/lane')),
                      len(section.findall('./right/lane')))
            require(actual == expected, 'Directional connector changed')
        recipe_path = ROOT / entry['fixture_recipe']
        recipe = read(recipe_path)
        require(recipe['generator']['sha256'] == sha(ROOT / recipe['generator']['source']),
                'Fixture generator changed')
        offline_name = 'offline-reference2' if suffix == 'reference' else 'offline-contrast'
        require(read(RUN / (offline_name + '.log'))['offline_passed'] is True,
                'Exact offline failed')
        compatibility_path = RUN / ('compatibility-' + suffix + '-final')
        compatibility = read(compatibility_path / 'compatibility.json')
        require(compatibility['passed'] is True and
                compatibility['negative_removed'] == 'raw.json' and
                compatibility['construction_sha256'] == construction_sha and
                compatibility['fixture_recipe_sha256'] == sha(recipe_path) and
                compatibility['runtime_manifest_sha256'] == runtime_sha,
                'Current-runtime compatibility failed or was rebound')
        report = read(compatibility_path / 'converted/adapter_report.json')
        coverage = report['occupancy_coverage']
        incomplete = [row['frame'] for row in coverage if row['incomplete_tracks'] or
                      any(not track['complete'] for track in row['tracks'])]
        require(report['frames'] == len(coverage) == 800 and not incomplete and
                report['occupancy_complete'] is True and
                report['atom_coverage']['atoms']['rel.occupies']['passed'] is True,
                'Mandatory occupancy incomplete')
        divider = [row for row in report['native_centre_lines']
                   if row['road_id'] in (404, 407, 409, 410) or
                   (row['road_id'] == 403 and row['section_id'] == 1)]
        require(not divider, 'Generated divider crosses open surface')
        saved_path = RUN / ('saved-' + suffix + '/v0001/processing.json')
        saved = read(saved_path)
        require(saved['passed'] is True and saved['recorded_only'] is True and
                saved['originals_preserved'] is True and
                saved['timestamp_joins'] == {'frames': 800, 'passed': True,
                                             'missing_original_trace_or_map': False} and
                saved['physical_acceptance_claimed'] is False and
                saved['legal_acceptance_claimed'] is False,
                'Recorded-only saved proof incomplete or overclaims acceptance')
        for target, source in (('pinned-' + suffix + '-offline.log', offline_name + '.log'),
                               ('pinned-' + suffix + '-compat.log', 'compatibility-' + suffix + '-final.log'),
                               ('pinned-' + suffix + '-saved.log', 'saved-' + suffix + '.log')):
            (WORK / target).write_bytes((RUN / source).read_bytes())
        measures = compatibility['measurement_examples']
        centers[suffix] = measures['turn_crossing_x_m']['value']
        cases[suffix] = {
            'case_id': entry['case_id'],
            'construction_sha256': construction_sha,
            'fixture_recipe_sha256': sha(recipe_path),
            'offline_log_sha256': sha(WORK / ('pinned-' + suffix + '-offline.log')),
            'compatibility_log_sha256': sha(WORK / ('pinned-' + suffix + '-compat.log')),
            'saved_log_sha256': sha(WORK / ('pinned-' + suffix + '-saved.log')),
            'compatibility_receipt_sha256': sha(compatibility_path / 'compatibility.json'),
            'saved_receipt_sha256': sha(saved_path),
            'mandatory_occupancy_frames_complete': len(coverage),
            'missing_source_negative_rejected': True,
            'measured_turn_crossing_x_m': centers[suffix],
            'authored_exception_location': measures['authored_exception_location']['value'],
        }
    require(len(roads) == 1, 'Cases use different road maps')
    require(centers['contrast'] - centers['reference'] == 45.0,
            'Measured comparison distance changed')
    require(cases['reference']['authored_exception_location'] is False and
            cases['contrast']['authored_exception_location'] is True,
            'Authored exception contrast changed')
    proof = {
        'format': 'c111662-shared-junction-current-runtime-probe-v1',
        'status': 'isolated_synthetic_cpu_proof_only',
        'runtime_manifest_sha256': runtime_sha,
        'manifest_sha256': sha(MANIFEST),
        'common_road_sha256': next(iter(roads)),
        'cases': cases,
        'measured_crossing_separation_m': 45.0,
        'original_native_observed': False,
        'selected_delivery_proved': False,
        'physical_or_legal_acceptance_claimed': False,
        'remaining': 'Source-fidelity review, original Native capture, selected-case delivery and legal comparison remain unproved.',
    }
    path = WORK / 'current-proof.json'
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(path), 'same_map': True,
                      'cases': list(cases), 'selected_delivery_proved': False}))


if __name__ == '__main__':
    main()
