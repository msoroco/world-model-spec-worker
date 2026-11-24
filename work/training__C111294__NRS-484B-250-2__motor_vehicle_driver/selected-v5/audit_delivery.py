"""Independent CPU audit of selected diagnostics, with a missing-source negative."""
import argparse
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_rows(path):
    require(path.is_file(), 'missing actor-history source')
    history = read(path)
    require(history.get('synthetic') is True and len(history.get('rows', [])) == 600,
            'actor-history source does not cover 600 synthetic frames')
    return history['rows']


def audit(case_id, negative=False):
    require(case_id in {BASE.name + '__controlled_1', BASE.name + '__controlled_2'},
            'wrong exact selected case')
    suffix = case_id.rsplit('__', 1)[1]
    source = BASE / 'selected-v3' / suffix / 'primary/sources'
    if negative:
        source_rows(source / 'missing-actor-history.json')
    rows = source_rows(source / 'actor-history.json')
    mapping = [json.loads(line) for line in (source / 'video_frames.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (source / 'capture/evidence.jsonl').read_text().splitlines()]
    require(len(mapping) == len(evidence) == len(rows), 'time join is incomplete')
    for frame, (row, joined, captured) in enumerate(zip(rows, mapping, evidence)):
        require(row['frame'] == joined['carla_frame'] == captured['original_frame'] == frame,
                'frame identities differ')
        require(abs(row['time_s'] - joined['time_s']) < 1e-9 and
                abs(row['time_s'] - captured['recording_time_s']) < 1e-9,
                'frame timestamps differ')
        require('body_xyz_m' in row['ego'] and 'body_xyz_m' in row['other'],
                'participant body history missing')
    manifest = read(BASE / 'selected-v5-manifest.json')
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    construction = BASE / entry['construction']
    require(sha(construction) == entry['construction_sha256'], 'construction changed')
    proof = BASE / 'selected-v5' / suffix / 'primary/proofs'
    public = read(proof / 'compatibility.json')
    saved = read(proof / 'saved-processing.json')
    require(public.get('passed') is True and public.get('construction_sha256') == sha(construction),
            'public compatibility does not bind selected construction')
    checks = {'four_camera_sources', 'actual_analysis', 'native_validation', 'lean_decoder',
              'final_decode', 'render', 'selected_measurements', 'negative_case_source'}
    require(checks <= set(public.get('checks', [])), 'public CPU proof omitted required checks')
    require(public.get('negative_removed') == 'actor-history.json' and
            public.get('negative_error_contains') in (proof / 'negative-analysis.log').read_text(),
            'public missing actor-source negative did not reject')
    require(saved.get('passed') is True and saved.get('recorded_only') is True and
            saved.get('originals_preserved') is True and saved.get('missing_evidence') is False,
            'recorded-only saved processing failed')
    require(saved.get('case_id') == case_id and saved.get('candidate_id') == 'primary',
            'saved processing selects another case')
    physical = read(BASE / 'selected-v5/physical-proofs' / suffix / 'proof.json')
    require(physical.get('construction_sha256') == sha(construction) and
            {x['kind'] for x in physical['fixtures']} ==
            {'complete_motion', 'incomplete_motion', 'missing_evidence'},
            'physical CPU fixture proof changed')
    require(not physical.get('original_native_motion_verified'),
            'CPU fixture cannot claim original Native motion')
    print(case_id + ': source join, public video/Core, saved processing and physical diagnostics pass')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case_id')
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    audit(args.case_id, args.negative)
