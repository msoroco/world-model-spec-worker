"""Audit the same-map directional intersection reference/contrast CPU pair."""
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
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    cases = {}
    roads = set()
    for suffix in ('reference', 'contrast'):
        prefix = '' if suffix == 'reference' else 'contrast-'
        manifest_path = HERE / ('directional-approach-experiment-manifest.json' if suffix == 'reference'
                                else 'directional-approach-contrast-experiment-manifest.json')
        manifest = read(manifest_path)
        require(manifest['runtime_manifest_sha256'] == runtime_sha and len(manifest['cases']) == 1,
                'Runtime or case mismatch: ' + suffix)
        entry = manifest['cases'][0]
        construction_path = HERE / entry['construction']
        require(entry['case_id'].endswith('__' + suffix) and
                entry['construction_sha256'] == sha(construction_path),
                'Exact construction changed: ' + suffix)
        construction = read(construction_path)
        files = {row['path']: row['content'] for row in construction['files']}
        road = files['road.xodr']
        road_sha = hashlib.sha256(road.encode()).hexdigest()
        roads.add(road_sha)
        road_nodes = {int(row.attrib['id']): row for row in ET.fromstring(road).findall('road')}
        require(set(road_nodes) == {403, 404, 405, 406, 407, 408, 409, 410, 411},
                'Directional map inventory changed')
        for ident, expected in ((403, (0, 3)), (411, (3, 0))):
            sections = road_nodes[ident].find('lanes').findall('laneSection')
            require(len(sections) == 1 and sections[0].attrib['s'] == '0',
                    'Approach lane transition: ' + suffix)
            left = sections[0].findall('./left/lane')
            right = sections[0].findall('./right/lane')
            require((len(left), len(right)) == expected and
                    all(row.attrib['type'] == 'driving' for row in left + right),
                    'Approach driving lanes changed: ' + suffix)
        require(road_nodes[409].find('./link/predecessor').attrib['elementId'] == '411',
                'Westbound connector detached')
        config_ref = 'work/' + HERE.name + '/native/selected-draft/' + suffix + '/config.json'
        config = json.loads(files[config_ref])
        require(config['road_sha256'] == road_sha and config['frames'] == 800 and
                config['rate_hz'] == 20 and config['original_native_observed'] is False and
                config['physical_success_claimed'] is False,
                'Config source or provenance changed')
        recipe_path = ROOT / entry['fixture_recipe']
        recipe = read(recipe_path)
        require(recipe['generator']['sha256'] == sha(ROOT / recipe['generator']['source']) and
                all(row['sha256'] == sha(ROOT / row['source']) for row in recipe['sources']),
                'Recipe source changed: ' + suffix)
        offline_log = WORK / ('pinned-' + prefix + 'offline.log')
        require(read(offline_log)['offline_passed'] is True,
                'Exact offline failed: ' + suffix)
        attempt = RUN / ('compatibility' if suffix == 'reference' else 'contrast-compatibility')
        receipt_path = attempt / 'compatibility.json'
        receipt = read(receipt_path)
        require(receipt['passed'] is True and receipt['negative_removed'] == 'raw.json' and
                receipt['construction_sha256'] == sha(construction_path) and
                receipt['fixture_recipe_sha256'] == sha(recipe_path) and
                receipt['runtime_manifest_sha256'] == runtime_sha and
                receipt['case_id'] == entry['case_id'] and receipt['candidate_id'] == 'primary',
                'Compatibility binding failed: ' + suffix)
        adapter_path = attempt / 'converted/adapter_report.json'
        adapter = read(adapter_path)
        coverage = adapter['occupancy_coverage']
        require(adapter['frames'] == len(coverage) == 800 and
                adapter['occupancy_complete'] is True and
                adapter['atom_coverage']['atoms']['rel.occupies']['passed'] is True and
                all(not row['incomplete_tracks'] and
                    all(track['complete'] for track in row['tracks']) for row in coverage) and
                403 not in {row['road_id'] for row in adapter['native_centre_lines']},
                'Mandatory occupancy or approach map failed: ' + suffix)
        saved_path = RUN / ('saved' if suffix == 'reference' else 'contrast-saved') / 'v0001/processing.json'
        saved = read(saved_path)
        require(saved['passed'] is True and saved['recorded_only'] is True and
                saved['originals_preserved'] is True and
                saved['physical_acceptance_claimed'] is False and
                saved['legal_acceptance_claimed'] is False,
                'Saved processing failed or overclaimed: ' + suffix)
        for label, source in ((prefix + 'compat-receipt.json', receipt_path),
                              (prefix + 'saved-receipt.json', saved_path)):
            require(source.stat().st_size <= 2 * 1024 * 1024, 'Receipt oversized')
            (WORK / label).write_bytes(source.read_bytes())
        cases[suffix] = {
            'case_id': entry['case_id'], 'manifest_sha256': sha(manifest_path),
            'construction_sha256': sha(construction_path), 'recipe_sha256': sha(recipe_path),
            'road_sha256': road_sha, 'offline_log_sha256': sha(offline_log),
            'compatibility_log_sha256': sha(WORK / ('pinned-' + prefix + 'compat.log')),
            'compatibility_receipt_sha256': sha(receipt_path),
            'adapter_report_sha256': sha(adapter_path),
            'saved_log_sha256': sha(WORK / ('pinned-' + prefix + 'saved.log')),
            'saved_receipt_sha256': sha(saved_path),
            'mandatory_occupancy_frames_complete': len(coverage),
            'crossing_x_m': receipt['measurement_examples']['turn_crossing_x_m']['value'],
            'authored_exception_location': receipt['measurement_examples'][
                'authored_exception_location']['value'],
        }
    require(len(roads) == 1, 'Reference/contrast roads differ')
    require(cases['reference']['authored_exception_location'] is False and
            cases['contrast']['authored_exception_location'] is True and
            44.9 < cases['contrast']['crossing_x_m'] - cases['reference']['crossing_x_m'] < 45.1,
            'Measured crossing comparison changed')
    proof = {
        'format': 'c111662-directional-approach-current-runtime-pair-v1',
        'status': 'isolated_synthetic_cpu_proof_only',
        'runtime_manifest_sha256': runtime_sha,
        'common_road_sha256': next(iter(roads)),
        'approach_shoulder_transition_present': False,
        'cases': cases, 'measured_crossing_separation_m':
            cases['contrast']['crossing_x_m'] - cases['reference']['crossing_x_m'],
        'selected_delivery_proved': False, 'original_native_observed': False,
        'physical_or_legal_acceptance_claimed': False,
        'remaining': 'Extend all fallbacks, review generated-road/source fidelity, integrate selected manifest and rerun selected delivery, comparison, semantic, queue and strict proofs.',
    }
    output = WORK / 'current-pair-proof.json'
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(output), 'common_road_sha256': next(iter(roads)),
                      'measured_crossing_separation_m': proof['measured_crossing_separation_m']}))


if __name__ == '__main__':
    main()
