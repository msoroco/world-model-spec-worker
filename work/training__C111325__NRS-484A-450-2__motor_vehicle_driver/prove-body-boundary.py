"""Diagnostic: first body corner, rather than centre, fixes crosswalk entry."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / '.runtime-work/c111325-body-boundary-proof'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load('crosswalk_fixture', HERE / 'prove-crosswalk-stop.py')
meter = load('crosswalk_meter', HERE / 'native/measure_stop.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    case = HERE.name + '__probe_1'
    baseline = fixture.rows(True)
    OUT.mkdir(parents=True, exist_ok=True)
    base_dir = OUT / 'baseline'
    fixture.write_fixture(base_dir, case, baseline)
    base = meter.measure(base_dir, case)
    assert base['pre_crosswalk_full_halt_observed'] is True

    # One front body vertex enters before the planned stop, while the centre
    # and other body vertices retain their original source-shaped trajectory.
    early = copy.deepcopy(baseline)
    for index in range(100, 120):
        early[index]['body_vertices_m'][0][1] = -10.9
    early_dir = OUT / 'early-front-corner'
    fixture.write_fixture(early_dir, case, early)
    crossed = meter.measure(early_dir, case)
    assert crossed['first_crosswalk_body_frame'] == 100
    assert crossed['pre_crosswalk_full_halt_observed'] is False
    assert crossed['longest_pre_crosswalk_stop_frames'] < 20

    # Changing the source after manifest hashing must be rejected.
    with (early_dir / 'native_samples.jsonl').open('a') as stream:
        stream.write('{}\n')
    try:
        meter.measure(early_dir, case)
    except ValueError as exc:
        rejection = str(exc)
        assert 'hash' in rejection.lower()
    else:
        raise AssertionError('Unbound body source accepted')

    proof = {
        'format': 'c111325-body-boundary-proof-v1',
        'case_id': case,
        'source_kind': 'synthetic_native_sample',
        'physical_observation_claimed': False,
        'legal_verdict': None,
        'meter_sha256': sha(HERE / 'native/measure_stop.py'),
        'fixture_builder_sha256': sha(HERE / 'prove-crosswalk-stop.py'),
        'baseline': base,
        'early_front_corner': crossed,
        'tampered_source_rejection': rejection,
    }
    path = HERE / 'body-boundary-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha(path),
                      'baseline_stop_frames': base['longest_pre_crosswalk_stop_frames'],
                      'early_entry_frame': crossed['first_crosswalk_body_frame']},
                     sort_keys=True))


if __name__ == '__main__':
    main()
