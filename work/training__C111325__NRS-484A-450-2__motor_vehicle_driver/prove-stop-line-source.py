"""Controlled synthetic-source test of the marked stop-line alternative."""
import hashlib
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_stop_line import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepared(index):
    target = ROOT / '.runtime-work/c111325-stop-line-source' / str(index)
    target.mkdir(parents=True, exist_ok=True)
    source = HERE / f'selected-source-probe-{index}'
    shutil.copyfile(HERE / 'native/road_stop_line.xodr', target / 'road.xodr')
    shutil.copyfile(source / 'native_samples.jsonl', target / 'native_samples.jsonl')
    case = HERE.name + f'__probe_{index}'
    (target / 'diagnostic-source-manifest.json').write_text(json.dumps({
        'case_id': case, 'source_kind': 'synthetic_native_sample',
        'sha256': {name: sha(target / name) for name in
                   ('road.xodr', 'native_samples.jsonl')}}, indent=2) + '\n')
    return target, case


def main():
    results = []
    for index, expected in ((1, True), (2, False)):
        folder, case = prepared(index)
        result = measure(folder, case)
        if result['pre_line_full_halt_observed'] is not expected:
            raise ValueError('Marked-line source contrast was not observed')
        results.append(result)
    folder, case = prepared(1)
    tree = ET.parse(folder / 'road.xodr')
    road = next(r for r in tree.getroot().findall('road') if r.get('id') == '1')
    road.find('objects').clear()
    tree.write(folder / 'road.xodr', encoding='unicode')
    try:
        measure(folder, case)
    except ValueError as error:
        if 'source hash differs' not in str(error):
            raise
    else:
        raise AssertionError('Changed road source hash was accepted')
    folder, case = prepared(1)
    tree = ET.parse(folder / 'road.xodr')
    road = next(r for r in tree.getroot().findall('road') if r.get('id') == '1')
    road.find('objects').clear()
    tree.write(folder / 'road.xodr', encoding='unicode')
    manifest = folder / 'diagnostic-source-manifest.json'
    identity = json.loads(manifest.read_text())
    identity['sha256']['road.xodr'] = sha(folder / 'road.xodr')
    manifest.write_text(json.dumps(identity, indent=2) + '\n')
    try:
        measure(folder, case)
    except ValueError as error:
        if 'Clearly marked stop-line source absent' not in str(error):
            raise
    else:
        raise AssertionError('Missing marked line was accepted')
    folder, case = prepared(1)
    tree = ET.parse(folder / 'road.xodr')
    road = next(r for r in tree.getroot().findall('road') if r.get('id') == '1')
    ET.SubElement(road.find('objects'), 'object', {
        'id': '903', 'name': 'crosswalk', 'type': 'crosswalk', 's': '225'})
    tree.write(folder / 'road.xodr', encoding='unicode')
    identity = json.loads(manifest.read_text())
    identity['sha256']['road.xodr'] = sha(folder / 'road.xodr')
    manifest.write_text(json.dumps(identity, indent=2) + '\n')
    try:
        measure(folder, case)
    except ValueError as error:
        if 'alternative has a crosswalk' not in str(error):
            raise
    else:
        raise AssertionError('Crosswalk branch was accepted as no-crosswalk')
    report = {'format': 'c111325-marked-line-source-software-proof-v1',
              'results': results, 'changed_road_source_rejected': True,
              'missing_line_rejected': True, 'crosswalk_present_rejected': True,
              'physical_line_appearance_verified': False,
              'legal_verdict_claimed': False}
    path = HERE / 'stop-line-source-proof.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'proof_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
