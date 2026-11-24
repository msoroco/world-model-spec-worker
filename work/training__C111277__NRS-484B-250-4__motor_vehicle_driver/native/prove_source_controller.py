"""Replay retained 600-frame source observations through the stop/yield policy."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from controller import InoperativeSignalController, Observation
from generate_fixture import make
from measure import load, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(source):
    index, geometry, signal, rows = load(source)
    measured = measure(source)
    controller = InoperativeSignalController(expected_stop_line_present=False)
    phases = []
    for row in rows:
        command = controller.step(Observation(
            frame=row['frame'],
            signal_installed=signal['installed'],
            signal_uncovered=signal['uncovered'],
            signal_inoperative=signal['inoperative_observed'],
            signal_governs_ego_lane=(signal['controlled_incoming_lane'] ==
                                    geometry['ego_incoming_lane']),
            stop_line_present=geometry['stop_line_present'],
            near_crosswalk_present=geometry['near_crosswalk_present'],
            ego_front_distance_to_boundary_m=(geometry['crosswalk_near_edge_x_m'] -
                                              row['ego_front_x_m']),
            ego_speed_mps=row['ego_speed_mps'],
            prior_stop_vehicle_approaching=(row['other_speed_mps'] <= 0.05 and
                                            not row['other_in_intersection']),
            vehicle_in_intersection=row['other_in_intersection']))
        phases.append(command.phase)
    return {'source_index_sha256': sha(source/'source-index.json'),
            'measurement': measured,
            'first_hold_frame': phases.index('hold') if 'hold' in phases else None,
            'first_yield_frame': phases.index('yield') if 'yield' in phases else None,
            'first_release_frame': phases.index('released') if 'released' in phases else None,
            'frames': len(phases)}


def main():
    assignment = Path(__file__).resolve().parents[1]
    root = assignment.parents[1]
    scratch = root/'.runtime-work/c111277/source-controller'
    scratch.mkdir(parents=True, exist_ok=True)
    for condition in ('halt', 'roll'):
        source = scratch/condition
        if source.exists():
            shutil.rmtree(source)
        make(source, condition)
    good = replay(scratch/'halt')
    if (good['first_hold_frame'] != 151 or good['first_yield_frame'] != 170 or
            good['first_release_frame'] != 241 or good['frames'] != 600):
        raise ValueError('Source-driven stop/yield timing changed')
    try:
        replay(scratch/'roll')
    except ValueError as exc:
        if 'crossed boundary before release' not in str(exc):
            raise
        roll_rejection = str(exc)
    else:
        raise ValueError('Rolling boundary crossing accepted')
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        changed = Path(temporary)/'halt'
        shutil.copytree(scratch/'halt', changed)
        path = changed/'native-rows.jsonl'
        path.write_bytes(path.read_bytes() + b'\n')
        try:
            replay(changed)
        except ValueError as exc:
            if 'source hash mismatch' not in str(exc):
                raise
        else:
            raise ValueError('Changed source accepted')
    proof = {'format': 'nrs-484b-250-4-source-controller-v1',
             'passed': True, 'halt': good,
             'roll_rejected': roll_rejection,
             'changed_source_rejected': True,
             'controller_sha256': sha(assignment/'native/controller.py'),
             'generator_sha256': sha(assignment/'native/generate_fixture.py'),
             'original_native_observed': False,
             'physical_signal_failure_confirmed': False,
             'legal_outcome_asserted': False}
    target = assignment/'native/source-controller-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'first_release_frame':
                      good['first_release_frame'], 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    sys.exit(main())
