"""Make source-consistent synthetic negative motion fixtures outside the return tree."""
import argparse
import json
import shutil
from pathlib import Path

ASSIGNMENT = 'training__C177225__NRS-484B-560-7b__bus_driver'
SOURCES = ('config.json', 'acquisition-provenance.json',
           'officer_signal_definition.json', 'bus_native_rows.jsonl',
           'officer_signal_rows.jsonl', 'video_frames.jsonl')


def run(source, destination, kind, suffix):
    source, destination = Path(source), Path(destination)
    if kind not in ('incomplete_motion', 'missing_evidence') or suffix not in ('reference', 'contrast'):
        raise ValueError('Select exact negative fixture kind and case')
    if destination.exists():
        raise ValueError('Retain prior generated negative fixture')
    provenance = json.loads((source / 'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind') != 'synthetic_fixture':
        raise ValueError('Negative diagnostic must derive from a synthetic source')
    config = json.loads((source / 'config.json').read_text())
    if config.get('case_id') != ASSIGNMENT + '__' + suffix:
        raise ValueError('Diagnostic case identity differs')
    destination.mkdir(parents=True)
    for name in SOURCES:
        shutil.copy2(source / name, destination / name)
    if kind == 'missing_evidence':
        (destination / 'officer_signal_rows.jsonl').unlink()
    else:
        path = destination / 'bus_native_rows.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != 600:
            raise ValueError('Expected full 600-frame raw bus fixture')
        if suffix == 'reference':
            for row in rows:
                row['velocity_native_xyz_mps'] = [1.0, 0.0, 0.0]
        else:
            for row in rows:
                row['station_m'] = -30.0 * config['direction']
        path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    print(json.dumps({'case_id': config['case_id'], 'kind': kind,
                      'provenance_kind': 'synthetic_fixture',
                      'source_count': len(SOURCES) - (kind == 'missing_evidence')}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--case-suffix', required=True)
    args = parser.parse_args()
    run(args.source, args.destination, args.kind, args.case_suffix)

if __name__ == '__main__':
    main()
