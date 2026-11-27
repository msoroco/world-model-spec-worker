"""Independent saved-source audit for the exact bridge and ground deliveries."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ('road.xodr', 'bridge-map.json', 'bridge-trace.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'overview.mkv', 'approach.mkv',
           'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    if not Path(path).is_file():
        raise ValueError('Missing source: ' + Path(path).name)
    return json.loads(Path(path).read_text())


def audit(case, candidate, attempt, processing, diagnostic=False, omit_source=None):
    selected_manifest = HERE / 'execution-manifest.json'
    if not selected_manifest.is_file():
        selected_manifest = HERE / 'draft-execution-manifest.json'
    manifest = read(selected_manifest)
    entry = next((e for e in manifest['cases'] if e['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    selected = entry if candidate == 'primary' else next(
        (e for e in entry['candidates'] if e['id'] == candidate), None)
    if selected is None:
        raise ValueError('Unknown selected candidate')
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != candidate or
            saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Selected saved processing or full-frame decode differs')
    stage = Path(saved['analysis_directory']).resolve()
    hashes = {}
    for name in SOURCES:
        if name == omit_source or not (stage / name).is_file():
            raise ValueError('Missing source: ' + name)
        hashes[name] = sha(stage / name)
    result = read(stage / 'result.json')
    report = read(stage / 'analysis-report.json')
    if (result.get('case_id') != case or
            len((stage / 'trace.jsonl').read_text().splitlines()) != 600 or
            len((stage / 'video_frames.jsonl').read_text().splitlines()) != 600):
        raise ValueError('Original trace or frame join differs')
    measurements = report.get('measurements', {})
    for key, method, names in (
            ('bridge_place', 'place_observation',
             ('bridge-map.json', 'bridge-trace.jsonl', 'video_frames.jsonl')),
            ('bridge_scope', 'bridge_scope_observation',
             ('bridge-map.json', 'bridge-trace.jsonl')),
            ('exception_context', 'exception_observation',
             ('bridge-trace.jsonl', 'road.xodr'))):
        measured = measurements.get(key, {})
        if measured.get('method') != method or any(
                measured.get('sources', {}).get(name) != hashes[name] for name in names):
            raise ValueError('Source-bound measurement differs: ' + key)
    value = measurements['bridge_scope']['value']
    expected = ['full'] if case.endswith('__true') else ['none']
    if value.get('relations_at_rest') != expected:
        raise ValueError('Selected bridge relation differs')
    if diagnostic:
        receipt = read(Path(attempt) / 'compatibility.json')
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != selected['construction_sha256']):
            raise ValueError('Diagnostic compatibility identity differs')
    else:
        provenance = read(Path(attempt) / 'acquisition-provenance.json')
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        context = measurements['exception_context']['value']
        if (context.get('traffic_conflict_necessity_verified') is not True or
                context.get('law_police_device_direction_verified') is not True or
                read(stage / 'bridge-map.json').get('physical_support_verified') is not True or
                result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
            raise ValueError('Original physical structure, activity or exception review incomplete')
    return {'format': 'c31675-independent-delivery-audit-v1', 'case_id': case,
            'candidate_id': candidate, 'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': sha(processing), 'source_sha256': hashes,
            'diagnostic_only': diagnostic, 'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source', choices=SOURCES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError('Source omission is diagnostic only')
    receipt = audit(args.case, args.candidate, args.attempt, args.processing,
                    args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError('Retain prior delivery audit result')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case,
                      'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
