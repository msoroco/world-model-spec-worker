"""Independently audit eight shoulder-free intersection CPU chains and pairs."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'directional-approach-experiment'
FALLBACK_RUN = ROOT / '.runtime-work/c111662-directional-fallbacks'
PRIMARY_RUN = ROOT / '.runtime-work/c111662-directional-approach'
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def locations(case, candidate):
    if candidate != 'primary':
        variant = WORK / case / candidate
        manifest = HERE / ('directional-approach-' + case + '-' + candidate + '-manifest.json')
        run = FALLBACK_RUN / case / candidate
        return variant, manifest, run
    prefix = '' if case == 'reference' else 'contrast-'
    manifest = HERE / ('directional-approach-experiment-manifest.json' if case == 'reference'
                       else 'directional-approach-contrast-experiment-manifest.json')
    run = PRIMARY_RUN
    return WORK, manifest, run


def main():
    runtime_sha = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    proof = {'format': 'c111662-directional-approach-eight-chain-audit-v1',
             'status': 'isolated_synthetic_cpu_proof_only',
             'runtime_manifest_sha256': runtime_sha, 'cases': {},
             'selected_delivery_proved': False, 'original_native_observed': False,
             'physical_or_legal_acceptance_claimed': False}
    roads = set()
    measured = {}
    for case in CASES:
        for candidate in CANDIDATES:
            name = case + '/' + candidate
            variant, manifest_path, run = locations(case, candidate)
            manifest = read(manifest_path)
            require(manifest['runtime_manifest_sha256'] == runtime_sha and
                    len(manifest['cases']) == 1, 'Manifest runtime/case changed: ' + name)
            entry = manifest['cases'][0]
            ref = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            construction_path = HERE / ref['construction']
            recipe_path = ROOT / entry['fixture_recipe']
            require(entry['case_id'].endswith('__' + case) and
                    ref['construction_sha256'] == sha(construction_path),
                    'Exact construction binding changed: ' + name)
            construction = read(construction_path)
            files = {item['path']: item['content'] for item in construction['files']}
            road = files['road.xodr']
            road_sha = hashlib.sha256(road.encode()).hexdigest()
            roads.add(road_sha)
            nodes = {int(node.attrib['id']): node for node in ET.fromstring(road).findall('road')}
            require(set(nodes) == {403, 404, 405, 406, 407, 408, 409, 410, 411},
                    'Road inventory changed: ' + name)
            for ident, lanes in ((403, (0, 3)), (411, (3, 0))):
                sections = nodes[ident].find('lanes').findall('laneSection')
                require(len(sections) == 1 and sections[0].attrib['s'] == '0',
                        'Approach shoulder transition: ' + name)
                left = sections[0].findall('./left/lane')
                right = sections[0].findall('./right/lane')
                require((len(left), len(right)) == lanes and
                        all(lane.attrib['type'] == 'driving' for lane in left + right),
                        'Approach driving lanes changed: ' + name)
            require(nodes[409].find('./link/predecessor').attrib['elementId'] == '411',
                    'Westbound connector changed: ' + name)
            config_ref = 'work/' + HERE.name + '/native/selected-draft/' + case + '/config.json'
            config = json.loads(files[config_ref])
            require(config['road_sha256'] == road_sha and config['frames'] == 800 and
                    config['rate_hz'] == 20 and
                    config['requested_approach_speed_mps'] ==
                    (3.0 if candidate == 'fallback1' else 5.0) and
                    config['camera_policy'] ==
                    ('elevated_overview' if candidate == 'fallback2' else 'standard') and
                    config['pre_turn_dwell_s'] ==
                    (2.0 if candidate == 'fallback3' else 0.0) and
                    config['original_native_observed'] is False and
                    config['physical_success_claimed'] is False and
                    config['legal_verdict'] is None,
                    'Candidate policy/provenance changed: ' + name)
            recipe = read(recipe_path)
            require(recipe['generator']['sha256'] == sha(ROOT / recipe['generator']['source']) and
                    all(source['sha256'] == sha(ROOT / source['source']) for source in recipe['sources']),
                    'Fixture source changed: ' + name)
            prefix = '' if candidate != 'primary' or case == 'reference' else 'contrast-'
            offline_log = variant / ('pinned-' + prefix + 'offline.log')
            compat_log = variant / ('pinned-' + prefix + 'compat.log')
            saved_log = variant / ('pinned-' + prefix + 'saved.log')
            require(read(offline_log)['offline_passed'] is True,
                    'Exact offline failed: ' + name)
            attempt = (run / 'compatibility' if candidate != 'primary' else
                       run / ('compatibility' if case == 'reference' else 'contrast-compatibility'))
            comp_path = attempt / 'compatibility.json'
            comp = read(comp_path)
            require(comp['passed'] is True and comp['negative_removed'] == 'raw.json' and
                    comp['case_id'] == entry['case_id'] and comp['candidate_id'] == candidate and
                    comp['construction_sha256'] == sha(construction_path) and
                    comp['fixture_recipe_sha256'] == sha(recipe_path) and
                    comp['runtime_manifest_sha256'] == runtime_sha,
                    'Positive/negative compatibility binding failed: ' + name)
            adapter_path = attempt / 'converted/adapter_report.json'
            adapter = read(adapter_path)
            coverage = adapter['occupancy_coverage']
            require(adapter['frames'] == len(coverage) == 800 and
                    adapter['occupancy_complete'] is True and
                    adapter['atom_coverage']['atoms']['rel.occupies']['passed'] is True and
                    all(not row['incomplete_tracks'] and
                        all(track['complete'] for track in row['tracks']) for row in coverage) and
                    403 not in {row['road_id'] for row in adapter['native_centre_lines']},
                    'Mandatory occupancy incomplete: ' + name)
            saved_path = (run / 'saved' if candidate != 'primary' else
                          run / ('saved' if case == 'reference' else 'contrast-saved')) / 'v0001/processing.json'
            saved = read(saved_path)
            require(saved['passed'] is True and saved['recorded_only'] is True and
                    saved['originals_preserved'] is True and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False and
                    saved['candidate_id'] == candidate and saved['case_id'] == entry['case_id'],
                    'Recorded-only saved failed or overclaimed: ' + name)
            measured[name] = comp['measurement_examples']
            proof['cases'][name] = {
                'case_id': entry['case_id'], 'candidate_id': candidate,
                'manifest_sha256': sha(manifest_path),
                'construction_sha256': sha(construction_path),
                'recipe_sha256': sha(recipe_path), 'road_sha256': road_sha,
                'offline_log_sha256': sha(offline_log),
                'compatibility_log_sha256': sha(compat_log),
                'compatibility_receipt_sha256': sha(comp_path),
                'adapter_report_sha256': sha(adapter_path),
                'saved_log_sha256': sha(saved_log),
                'saved_receipt_sha256': sha(saved_path),
                'mandatory_occupancy_frames_complete': len(coverage),
                'measurement_examples': comp['measurement_examples'],
            }
    require(len(roads) == 1, 'Comparison road maps differ')
    for candidate in CANDIDATES:
        ref = measured['reference/' + candidate]
        contrast = measured['contrast/' + candidate]
        require(ref['authored_exception_location']['value'] is False and
                contrast['authored_exception_location']['value'] is True and
                44.9 < contrast['turn_crossing_x_m']['value'] -
                ref['turn_crossing_x_m']['value'] < 45.1,
                'Same-policy crossing comparison changed: ' + candidate)
    proof['common_road_sha256'] = next(iter(roads))
    proof['candidate_chains_passed'] = len(proof['cases'])
    proof['same_policy_comparison_pairs_passed'] = len(CANDIDATES)
    proof['approach_shoulder_transition_present'] = False
    proof['remaining'] = ('Review generated-road/source fidelity, integrate selected manifest, '
                          'rerun all 16 selected chains and independent delivery, comparison, '
                          'physical, semantic, queue and strict checks.')
    output = WORK / 'current-eight-proof.json'
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_chains_passed': len(proof['cases']),
                      'same_policy_comparison_pairs_passed': len(CANDIDATES),
                      'proof_sha256': sha(output)}))


if __name__ == '__main__':
    main()
