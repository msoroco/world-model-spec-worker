"""Audit current-runtime divided-highway directional-carriageway CPU probes."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'split-divided-experiment'
RUN = ROOT / '.runtime-work/c111662-split-divided'
MANIFEST = HERE / 'split-divided-experiment-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    manifest = read(MANIFEST)
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    require(manifest['runtime_manifest_sha256'] == runtime_sha, 'Probe binds another runtime')
    require(len(manifest['cases']) == 2, 'Divided case pair required')
    roads = set()
    cases = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        require(suffix in ('divided_reference', 'divided_opening') and suffix not in cases,
                'Duplicate or unexpected case')
        construction_path = HERE / entry['construction']
        construction_sha = sha(construction_path)
        require(entry['construction_sha256'] == construction_sha, 'Construction binding changed')
        construction = read(construction_path)
        road = next(item['content'] for item in construction['files'] if item['path'] == 'road.xodr')
        road_sha = hashlib.sha256(road.encode()).hexdigest()
        roads.add(road_sha)
        segments = {int(item.attrib['id']): item for item in ET.fromstring(road).findall('road')}
        require(set(segments) == {503, 504, 505, 506, 507, 508},
                'Divided carriageway segments changed')
        for ident in (503, 504, 505):
            section = segments[ident].find('./lanes/laneSection')
            require(not section.findall('./left/lane') and
                    len(section.findall('./right/lane')) == 3,
                    'Eastbound carriageway lanes changed')
        for ident in (506, 507, 508):
            section = segments[ident].find('./lanes/laneSection')
            left = {int(lane.attrib['id']): lane for lane in section.findall('./left/lane')}
            require(set(left) == {1, 2, 3, 4} and
                    not section.findall('./right/lane'), 'Westbound carriageway lanes changed')
            require(left[1].attrib['type'] == ('driving' if ident == 507 else 'median') and
                    left[1].find('roadMark').attrib['type'] ==
                    ('broken' if ident == 507 else 'solid'),
                    'Authored median or crossing opening changed')
        recipe_path = ROOT / entry['fixture_recipe']
        recipe = read(recipe_path)
        require(recipe['generator']['sha256'] == sha(ROOT / recipe['generator']['source']),
                'Fixture generator changed')
        offline_log = RUN / ('offline-' + suffix + '-v2.log')
        require(read(offline_log)['offline_passed'] is True, 'Exact offline failed')
        compatibility_path = RUN / ('compatibility-' + suffix)
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
                report['atom_coverage']['atoms']['rel.occupies']['passed'] is True and
                not report['native_centre_lines'], 'Mandatory divided occupancy incomplete')
        saved_path = RUN / ('saved-' + suffix + '/v0001/processing.json')
        saved = read(saved_path)
        require(saved['passed'] is True and saved['recorded_only'] is True and
                saved['originals_preserved'] is True and
                saved['physical_acceptance_claimed'] is False and
                saved['legal_acceptance_claimed'] is False,
                'Recorded-only saved proof incomplete or overclaims acceptance')
        for target, source in (('pinned-' + suffix + '-offline.log',
                                'offline-' + suffix + '-v2.log'),
                               ('pinned-' + suffix + '-compat.log',
                                'compatibility-' + suffix + '.log'),
                               ('pinned-' + suffix + '-saved.log',
                                'saved-' + suffix + '.log')):
            (WORK / target).write_bytes((RUN / source).read_bytes())
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
            'authored_divided_opening': compatibility['measurement_examples'][
                'authored_divided_opening']['value'],
        }
    require(len(roads) == 1, 'Divided pair uses different maps')
    require(cases['divided_reference']['authored_divided_opening'] is False and
            cases['divided_opening']['authored_divided_opening'] is True,
            'Opening comparison changed')
    proof = {
        'format': 'c111662-split-divided-current-runtime-probe-v1',
        'status': 'isolated_synthetic_cpu_proof_only',
        'runtime_manifest_sha256': runtime_sha,
        'manifest_sha256': sha(MANIFEST),
        'common_road_sha256': next(iter(roads)),
        'cases': cases,
        'original_native_observed': False,
        'selected_delivery_proved': False,
        'physical_or_legal_acceptance_claimed': False,
        'remaining': 'Review split-road physical connectivity and source fidelity; rebind all selected candidates and independent delivery audits.',
    }
    path = WORK / 'current-proof.json'
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(path), 'same_map': True,
                      'cases': list(cases), 'selected_delivery_proved': False}))


if __name__ == '__main__':
    main()
