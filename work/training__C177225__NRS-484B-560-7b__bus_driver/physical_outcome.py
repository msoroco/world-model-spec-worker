"""Source-bound physical outcome assessment for the two C177225 bus cases.

A diagnostic can show that the requested maneuver was not measured, but a
synthetic positive remains unverified. Only sealed original Native sources can
support a complete-motion result. No result here determines legal compliance.
"""
import argparse
import hashlib
import json
from pathlib import Path

from measure_direction import derive_observation
from officer_direction import Crossing, OfficerStop

ASSIGNMENT = 'training__C177225__NRS-484B-560-7b__bus_driver'
SOURCES = ('config.json', 'officer_signal_definition.json', 'bus_native_rows.jsonl',
           'officer_signal_rows.jsonl', 'video_frames.jsonl')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def assess(folder, case_id):
    folder = Path(folder)
    if case_id not in (ASSIGNMENT + '__reference', ASSIGNMENT + '__contrast'):
        raise ValueError('Unknown exact bus/officer case')
    available = {name: _sha(folder / name) for name in SOURCES if (folder / name).is_file()}
    missing = sorted(set(SOURCES) - set(available))
    provenance_path = folder / 'acquisition-provenance.json'
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    kind = provenance.get('provenance_kind', 'unverified')
    sealed = folder / 'capture-seal.json'
    if kind == 'native':
        if not sealed.is_file():
            missing.append('capture-seal.json')
        else:
            seal = json.loads(sealed.read_text())
            if (seal.get('provenance_kind') != 'native' or
                    seal.get('format') != 'worker-sealed-capture' or
                    seal.get('diagnostic_fixture') is not False or
                    seal.get('frames') != 600 or
                    seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
                    seal.get('restoration', {}).get('restored') is not True):
                raise ValueError('Invalid Native capture seal')
            for name, digest in available.items():
                if seal.get('sources', {}).get(name) != digest:
                    raise ValueError('Sealed original source differs: ' + name)
            available['capture-seal.json'] = _sha(sealed)
    error = None
    observation = None
    config = None
    if not missing:
        try:
            config = json.loads((folder / 'config.json').read_text())
            if config.get('case_id') != case_id or config.get('frames') != 600 or config.get('rate_hz') != 20:
                raise ValueError('Exact case or capture profile differs')
            signal = OfficerStop(**json.loads((folder / 'officer_signal_definition.json').read_text()))
            bus = _rows(folder / 'bus_native_rows.jsonl')
            officer = _rows(folder / 'officer_signal_rows.jsonl')
            mapping = _rows(folder / 'video_frames.jsonl')
            if len(bus) != 600 or len(officer) != 600 or len(mapping) != 600:
                raise ValueError('Incomplete 600-frame source join')
            first_time = mapping[0].get('time_s')
            if not isinstance(first_time, (int, float)) or any(row.get('video_frame') != i or
                   not isinstance(row.get('time_s'), (int, float)) or
                   abs(row['time_s'] - (first_time + i / 20)) > 1e-4
                   for i, row in enumerate(mapping)):
                raise ValueError('Video frame index or 20 Hz timestamp differs')
            observation = derive_observation(Crossing(), signal, bus, officer, mapping,
                                             source_kind=('original_native' if kind == 'native' else 'synthetic_native_sample'))
        except (OSError, ValueError, KeyError, TypeError) as failure:
            error = str(failure)
    expected = ('observed_complete_stop_before_line' if case_id.endswith('__reference')
                else 'observed_crossing_entry')
    observed = bool(observation[expected]) if observation is not None else None
    status = ('unverified' if observed is None or (observed and kind != 'native')
              else 'met' if observed else 'not_met')
    method = ('600-frame original bus velocity/station, officer direction and video-frame join; '
              'reference requires measured stop before line, contrast requires measured crossing entry')
    check = {
        'status': status, 'method': method, 'sources': available,
        'missing_evidence': missing + ([error] if error else []),
        'observed_target': observed, 'target_observable': expected,
        'physical_causation_claimed': False, 'legal_verdict_claimed': False
    }
    return {
        'format': 'c177225-physical-outcome-v1', 'case_id': case_id,
        'provenance_kind': kind, 'diagnostic_fixture': kind != 'native',
        'physical_checks': {'maneuver': check},
        'maneuver_completed': status == 'met',
        'realized_observables': ({expected: {'value': True, 'source': 'bus_native_rows.jsonl',
                                             'method': method}} if status == 'met' else {}),
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.attempt, args.case)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': result['physical_checks']['maneuver']['status'],
                      'provenance_kind': result['provenance_kind']}))


if __name__ == '__main__':
    main()
