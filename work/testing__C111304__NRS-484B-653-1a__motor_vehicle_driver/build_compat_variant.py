"""Derive one explicit synthetic diagnostic case from sealed C111304 source rows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

from encounter import CASES
import build_compat_capture

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = HERE / 'fixtures/person_north_early'
SOURCE_NAMES = ('access-review.json', 'access-source.txt', 'camera-plan.json',
                'site.json', 'native-receipt.json', 'original-history.jsonl',
                'original-packets.jsonl', 'original-cameras.jsonl',
                'trace.jsonl', 'video_frames.jsonl', 'acquisition-provenance.json')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def write_rows(path: Path, values: list[dict]) -> None:
    path.write_text(''.join(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'
                            for value in values), encoding='utf-8')


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def main(suffix: str) -> None:
    case = next((case for case in CASES if case.case_id == suffix), None)
    if case is None or suffix == 'person_north_early':
        raise ValueError('select another exact C111304 case')
    destination = HERE / 'fixtures' / suffix
    if destination.exists():
        raise ValueError('diagnostic variant already exists: ' + suffix)
    scratch = REPO / '.runtime-work' / ('c111304-fixture-seed-' + suffix)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    for name in SOURCE_NAMES:
        shutil.copyfile(BASE / name, scratch / name)
    access = scratch / 'access-source.txt'
    review_path = scratch / 'access-review.json'
    site_path = scratch / 'site.json'
    review = json.loads(review_path.read_text(encoding='utf-8'))
    site = json.loads(site_path.read_text(encoding='utf-8'))
    if case.public_access_basis == 'public_access_premises':
        access.write_text('Diagnostic synthetic public-access premises, not an original property record.\n', encoding='utf-8')
        site['site_id'] = 'diagnostic-public-access-premises'
    review['public_access_basis'] = case.public_access_basis
    review['source_sha256'] = sha(access)
    write_json(review_path, review)
    site['public_access_basis'] = case.public_access_basis
    site['public_access_review_sha256'] = sha(review_path)
    write_json(site_path, site)
    site_hash = sha(site_path)
    packets = read_rows(scratch / 'original-packets.jsonl')
    history = read_rows(scratch / 'original-history.jsonl')
    traces = read_rows(scratch / 'trace.jsonl')
    for packet, record, trace in zip(packets, history, traces):
        ego = packet['actors']['ego']
        if case.approach == 'southbound':
            ego['xy'][0] = -abs(ego['xy'][0])
            ego['heading_deg'] = 180.0
        if case.crossing_release_s > 1.0:
            packet['actors']['occupant']['xy'][1] += case.crossing_release_s - 1.0
        if suffix == 'property_far':
            packet['actors']['property']['xy'][1] += 8.0
        controls = packet['control']
        controls['ego_target_speed_mps'] = case.ego_speed_mps
        controls['crossing_target_speed_mps'] = case.crossing_speed_mps
        controls['crossing_release_s'] = case.crossing_release_s
        record['case_id'] = HERE.name + '__' + suffix
        record['site_sha256'] = site_hash
        record['public_access_basis'] = case.public_access_basis
        record['ego_xy'] = ego['xy']
        record['occupant_xy'] = packet['actors']['occupant']['xy']
        record['property_xy'] = packet['actors']['property']['xy']
        record['ego_speed_mps'] = ego['speed_mps']
        record['crossing_speed_mps'] = packet['actors']['crossing_vehicle']['speed_mps']
        record['source_sha256'] = hashlib.sha256(json.dumps(
            packet, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        record['control_command_source_sha256'] = hashlib.sha256(json.dumps(
            controls, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        trace['position_m'] = [*ego['xy'], ego['z']]
        trace['position'] = dict(zip(('x', 'y', 'z'), trace['position_m']))
        trace['heading_deg'] = ego['heading_deg']
        trace['velocity_mps'] = [ego['speed_mps'] * (-1 if case.approach == 'southbound' else 1), 0.0, 0.0]
    write_rows(scratch / 'original-packets.jsonl', packets)
    write_rows(scratch / 'original-history.jsonl', history)
    write_rows(scratch / 'trace.jsonl', traces)
    receipt_path = scratch / 'native-receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt['case_id'] = HERE.name + '__' + suffix
    receipt['public_access_basis'] = case.public_access_basis
    receipt['site_sha256'] = site_hash
    receipt['ego_target_speed_mps'] = case.ego_speed_mps
    receipt['crossing_target_speed_mps'] = case.crossing_speed_mps
    receipt['crossing_release_s'] = case.crossing_release_s
    for field, name in (('original_history_sha256', 'original-history.jsonl'),
                        ('original_packets_sha256', 'original-packets.jsonl'),
                        ('original_trace_sha256', 'trace.jsonl')):
        receipt[field] = sha(scratch / name)
    write_json(receipt_path, receipt)
    shutil.copytree(scratch, destination)
    generator_path = HERE / ('fixture-generator-' + suffix + '.json')
    generator = json.loads((HERE / 'fixture-generator-person_north_early.json').read_text())
    generator['graphs'] = []
    generator_path.write_text(json.dumps(generator, separators=(',', ':')) + '\n', encoding='utf-8')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name, 'source': 'work/' + HERE.name + '/fixtures/' + suffix + '/' + name,
                           'sha256': sha(destination / name)} for name in SOURCE_NAMES],
              'generator': {'source': 'work/' + HERE.name + '/fixture-generator-' + suffix + '.json',
                            'sha256': sha(generator_path)}}
    write_json(HERE / ('fixture-recipe-' + suffix + '.json'), recipe)
    build_compat_capture.main(suffix)
    print('created sealed synthetic diagnostic fixture for', suffix)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: build_compat_variant.py CASE_SUFFIX')
    main(sys.argv[1])
