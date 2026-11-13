"""Verify exact sign-angle source recipes and recorded-only CPU replays."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from build_sign_angle_cases import ANGLES_RAD

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREFIX = ROOT.name + '__yield_nearest_view_sign_angle_'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = read(ROOT / 'sign-angle-compatibility-manifest.json')
    require(len(manifest['cases']) == 3, 'Three exact sign-angle cases required')
    receipts = []
    fixed_rows = None
    for (angle, label), entry in zip(ANGLES_RAD, manifest['cases']):
        require(entry['case_id'] == PREFIX + label, 'Sign-angle identity differs')
        construction = ROOT / entry['construction']
        require(sha(construction) == entry['construction_sha256'], 'Construction hash changed')
        recipe_path = REPO / entry['fixture_recipe']
        recipe = read(recipe_path)
        for item in recipe['sources']:
            source = REPO / item['source']
            require(sha(source) == item['sha256'], 'Original recipe source changed')
        require(sha(REPO / recipe['generator']['source']) == recipe['generator']['sha256'],
                'Diagnostic generator source changed')
        road = ET.parse(REPO / recipe['sources'][next(i for i, item in
                            enumerate(recipe['sources']) if item['path'] == 'road.xodr')]['source'])
        sign = road.getroot().find("./road[@id='158190']/signals/signal")
        require(sign is not None and abs(float(sign.attrib['hOffset']) - angle) < 1e-12,
                'Original authored sign angle differs')
        control_source = REPO / next(item['source'] for item in recipe['sources']
                                     if item['path'] == 'control_inventory.jsonl')
        controls = rows(control_source)
        require(len(controls) == 600, 'Original sign inventory lacks full duration')
        expected_yaw = angle * 180 / 3.141592653589793
        require(all(row['frame'] == 100 + index
                    and row['yield_sign']['actor_id'] == 12
                    and abs(row['yield_sign']['native_rotation_deg']['yaw'] - expected_yaw) < 1e-9
                    for index, row in enumerate(controls)),
                'Original diagnostic sign-pose readback differs')
        stable = [{**row, 'yield_sign': {**row['yield_sign'],
                   'native_rotation_deg': None}} for row in controls]
        if fixed_rows is None:
            fixed_rows = stable
        else:
            require(stable == fixed_rows, 'Fixed control inventory changed')
        compat = REPO / f'.runtime-work/c158190-sign-angle-{label}-compat-v1'
        positive = read(compat / 'compatibility.json')
        require(positive.get('passed') is True and positive.get('case_id') == entry['case_id']
                and positive.get('construction_sha256') == entry['construction_sha256']
                and {'selected_measurements', 'negative_case_source', 'lean_decoder',
                     'final_decode'} <= set(positive.get('checks', [])),
                'Compatibility proof incomplete')
        saved = REPO / f'.runtime-work/c158190-sign-angle-{label}-saved-v1/v0001/processing.json'
        processed = read(saved)
        require(processed.get('passed') is True
                and processed.get('recorded_only') is True
                and processed.get('originals_preserved') is True
                and processed.get('physical_acceptance_claimed') is False
                and processed.get('legal_acceptance_claimed') is False,
                'Recorded-only saved proof incomplete')
        receipts.append({'case_id': entry['case_id'], 'authored_hOffset_rad': angle,
                         'diagnostic_yaw_deg': expected_yaw,
                         'construction_sha256': sha(construction),
                         'recipe_sha256': sha(recipe_path),
                         'control_source_sha256': sha(control_source),
                         'compatibility_sha256': sha(compat / 'compatibility.json'),
                         'saved_processing_sha256': sha(saved)})
    print(json.dumps({'format': 'c158190-sign-angle-saved-source-proof',
                      'cases': receipts, 'all_passed': True,
                      'source_kind': 'synthetic Native-shaped diagnostics',
                      'native_sign_pose_proven': False,
                      'original_pixel_face_proven': False,
                      'legal_conclusion': 'unresolved'}, indent=2))


if __name__ == '__main__':
    main()
