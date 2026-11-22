"""Audit the source-bound directional approach CPU construction and receipts."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'directional-approach-experiment'
RUN = ROOT / '.runtime-work/c111662-directional-approach'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    manifest_path = HERE / 'directional-approach-experiment-manifest.json'
    manifest = read(manifest_path)
    require(manifest['runtime_manifest_sha256'] ==
            sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json'), 'Runtime changed')
    require(len(manifest['cases']) == 1, 'Expected one reference case')
    entry = manifest['cases'][0]
    require(entry['case_id'].endswith('__reference') and
            entry['construction_sha256'] == sha(HERE / entry['construction']),
            'Exact construction binding changed')
    construction = read(HERE / entry['construction'])
    files = {row['path']: row['content'] for row in construction['files']}
    road = files['road.xodr']
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    roads = {int(row.attrib['id']): row for row in ET.fromstring(road).findall('road')}
    require(set(roads) == {403, 404, 405, 406, 407, 408, 409, 410, 411},
            'Directional road inventory changed')
    for ident, expected in ((403, (0, 3)), (411, (3, 0)),
                            (404, (0, 3)), (409, (3, 0))):
        sections = roads[ident].find('lanes').findall('laneSection')
        require(len(sections) == 1 and sections[0].attrib['s'] == '0',
                'Lane transition returned: ' + str(ident))
        left = sections[0].findall('./left/lane')
        right = sections[0].findall('./right/lane')
        require((len(left), len(right)) == expected and
                all(row.attrib['type'] == 'driving' for row in left + right),
                'Approach driving lane missing: ' + str(ident))
    require(roads[409].find('./link/predecessor').attrib['elementId'] == '411',
            'Westbound approach link changed')
    config_path = 'work/' + HERE.name + '/native/selected-draft/reference/config.json'
    config = json.loads(files[config_path])
    require(config['road_sha256'] == road_sha and config['frames'] == 800 and
            config['rate_hz'] == 20 and config['original_native_observed'] is False,
            'Config road or provenance changed')
    recipe = read(ROOT / entry['fixture_recipe'])
    require(recipe['generator']['sha256'] == sha(ROOT / recipe['generator']['source']) and
            all(row['sha256'] == sha(ROOT / row['source']) for row in recipe['sources']),
            'Fixture source changed')
    offline = read(WORK / 'pinned-offline.log')
    require(offline['offline_passed'] is True, 'Exact offline failed')
    comp_path = RUN / 'compatibility'
    comp = read(comp_path / 'compatibility.json')
    require(comp['passed'] is True and comp['negative_removed'] == 'raw.json' and
            comp['construction_sha256'] == sha(HERE / entry['construction']) and
            comp['fixture_recipe_sha256'] == sha(ROOT / entry['fixture_recipe']) and
            comp['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256'] and
            comp['measurement_examples']['authored_exception_location']['value'] is False,
            'Compatibility or negative binding failed')
    adapter_path = comp_path / 'converted/adapter_report.json'
    adapter = read(adapter_path)
    coverage = adapter['occupancy_coverage']
    require(adapter['frames'] == len(coverage) == 800 and
            adapter['occupancy_complete'] is True and
            adapter['atom_coverage']['atoms']['rel.occupies']['passed'] is True and
            all(not row['incomplete_tracks'] and
                all(track['complete'] for track in row['tracks']) for row in coverage),
            'Mandatory occupancy incomplete')
    require(403 not in {row['road_id'] for row in adapter['native_centre_lines']},
            'Approach generated centreline returned')
    saved_path = RUN / 'saved/v0001/processing.json'
    saved = read(saved_path)
    require(saved['passed'] is True and saved['recorded_only'] is True and
            saved['originals_preserved'] is True and
            saved['physical_acceptance_claimed'] is False and
            saved['legal_acceptance_claimed'] is False,
            'Saved processing failed or overclaimed')
    for label, source in (('compat-receipt.json', comp_path / 'compatibility.json'),
                          ('saved-receipt.json', saved_path)):
        require(source.stat().st_size <= 2 * 1024 * 1024, 'Receipt oversized')
        (WORK / label).write_bytes(source.read_bytes())
    proof = {
        'format': 'c111662-directional-approach-current-runtime-probe-v1',
        'status': 'isolated_synthetic_cpu_proof_only',
        'manifest_sha256': sha(manifest_path),
        'construction_sha256': sha(HERE / entry['construction']),
        'road_sha256': road_sha,
        'recipe_sha256': sha(ROOT / entry['fixture_recipe']),
        'offline_log_sha256': sha(WORK / 'pinned-offline.log'),
        'compatibility_log_sha256': sha(WORK / 'pinned-compat.log'),
        'compatibility_receipt_sha256': sha(WORK / 'compat-receipt.json'),
        'adapter_report_sha256': sha(adapter_path),
        'saved_log_sha256': sha(WORK / 'pinned-saved.log'),
        'saved_receipt_sha256': sha(WORK / 'saved-receipt.json'),
        'mandatory_occupancy_frames_complete': len(coverage),
        'approach_shoulder_transition_present': False,
        'crossing_x_m': comp['measurement_examples']['turn_crossing_x_m']['value'],
        'selected_delivery_proved': False,
        'original_native_observed': False,
        'physical_or_legal_acceptance_claimed': False,
        'remaining': 'Prove contrast on the same map, extend all fallbacks, review generated-road source fidelity, integrate selected manifest and rerun selected delivery gates.',
    }
    output = WORK / 'current-proof.json'
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(output),
                      'mandatory_occupancy_frames_complete': len(coverage),
                      'approach_shoulder_transition_present': False}))


if __name__ == '__main__':
    main()
