"""Independent signed-case receipt and unsigned comparison audit."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__ordinary_red_signed'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(index=None):
    if index is None:
        index = json.loads((ROOT /
            'selected-ordinary_red_signed-current-receipts/proof-index.json').read_text())
    require(index.get('case_id') == CASE and index.get('candidate_count') == 4 and
            set(index.get('candidates', {})) == set(CANDIDATES) and
            index.get('original_native_observed') is False and
            index.get('physical_acceptance_claimed') is False,
            'Signed candidate index differs')
    counts = {}
    for candidate in CANDIDATES:
        row = index['candidates'][candidate]
        tag = 'signed/' + candidate
        manifest = ROOT / row['manifest']
        construction = ROOT / row['construction']
        require(sha(manifest) == row['manifest_sha256'] and
                sha(construction) == row['construction_sha256'],
                'Signed source hash changed: ' + tag)
        entry = next(e for e in json.loads(manifest.read_text())['cases']
                     if e['case_id'] == CASE)
        require(sha(REPO / entry['fixture_recipe']) == row['fixture_recipe_sha256'],
                'Signed fixture changed: ' + tag)
        package = json.loads(construction.read_text())
        files = {f['path']: f['content'] for f in package['files']}
        config = json.loads(files['config.json'])
        require(config['candidate_id'] == candidate and
                config['sign_classes'] == ['no_parking'] and
                config['service_class'] == 'ordinary' and
                config['native_blueprint'] == 'vehicle.tesla.model3',
                'Signed configuration differs: ' + tag)
        ordinary = json.loads((ROOT / ('selected-primary/reference/construction.json'
            if candidate == 'primary' else
            'selected-fallbacks/reference/' + candidate + '/construction.json')).read_text())
        ordinary_files = {f['path']: f['content'] for f in ordinary['files']}
        ordinary_config = json.loads(ordinary_files['config.json'])
        require(files['requested-tracks.jsonl'] ==
                ordinary_files['requested-tracks.jsonl'] and
                files['parking_controller.py'] ==
                ordinary_files['parking_controller.py'] and
                files['assignment-source.json'] ==
                ordinary_files['assignment-source.json'] and
                files['case-plan.json'] == ordinary_files['case-plan.json'] and
                config['requested_target_x_m'] ==
                ordinary_config['requested_target_x_m'] == 40 and
                config['requested_approach_frames'] ==
                ordinary_config['requested_approach_frames'] and
                config['camera_policy'] == ordinary_config['camera_policy'],
                'Unsigned/signed fixed conditions differ: ' + candidate)
        signed_xml = ET.fromstring(files['red-curb-road.xodr'])
        unsigned_xml = ET.fromstring(ordinary_files['red-curb-road.xodr'])
        require(len(signed_xml.findall('.//signals/signal')) == 1 and
                not unsigned_xml.findall('.//signals/signal'),
                'Signed comparison lacks sole signal difference')
        signed_road = signed_xml.find('road')
        signed_road.remove(signed_road.find('signals'))
        require(ET.canonicalize(ET.tostring(signed_xml, encoding='unicode'),
                                strip_text=True) ==
                ET.canonicalize(ET.tostring(unsigned_xml, encoding='unicode'),
                                strip_text=True),
                'Signed/unsigned roads differ beyond sign geometry')
        receipts = {}
        for name, spec in row['receipts'].items():
            path = ROOT / spec['path']
            require(sha(path) == spec['sha256'], 'Signed receipt changed: ' + tag + '/' + name)
            receipts[name] = (path.read_text() if path.suffix == '.log'
                              else json.loads(path.read_text()))
        for stage, checksum in row['logs'].items():
            prefix = 'update024-signed-' + candidate
            require(sha(ROOT / (prefix + '-' + stage + '.log')) == checksum,
                    'Signed command log changed: ' + tag + '/' + stage)
        result = receipts['result']
        analysis = receipts['analysis']
        observation = analysis['measurements']['signed_curb_observation']['value']
        require('OK' in receipts['offline_test'] and
                'Missing required source: native-map-readback.json' in
                    receipts['negative_analysis'] and
                receipts['compatibility']['passed'] is True and
                receipts['saved']['passed'] is True and
                receipts['saved']['originals_preserved'] is True and
                receipts['saved']['missing_evidence'] is False and
                receipts['saved']['timestamp_joins']['frames'] == 240 and
                result['case_id'] == CASE and
                result['provenance_kind'] == 'synthetic_local_diagnostic' and
                result['accepted'] is False and
                observation['source_kind'] == 'synthetic_native_sample' and
                observation['displayed_sign_classes'] == ['no_parking'] and
                observation['native_blueprint'] == 'vehicle.tesla.model3' and
                observation['sign_over_red_extent'] is True and
                observation['statutory_exception_applies'] is None and
                observation['physical_acceptance_claimed'] is False and
                observation['legal_verdict'] is None,
                'Signed source-bound positive/negative proof differs: ' + tag)
        counts[candidate] = result['measured_values']['red_curb_stopped_frames']
        require(counts[candidate] == row['synthetic_red_stopped_frames'],
                'Signed stopped interval differs: ' + tag)
    require(counts == dict(zip(CANDIDATES, (119, 59, 119, 149))),
            'Signed candidate intervals differ')
    return {'format': 'c150142-signed-cpu-audit-v1', 'passed': True,
            'case_id': CASE, 'candidate_count': 4, 'counts': counts,
            'original_native_observed': False, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
