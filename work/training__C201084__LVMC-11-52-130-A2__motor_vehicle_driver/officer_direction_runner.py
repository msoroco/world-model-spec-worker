"""Draft Native runner and saved-source audit for an officer actor probe."""
import hashlib
import json
from pathlib import Path

from fire_lane_survey import require
from native_runner import run as run_reference
from officer_direction_capture import acquire as capture_with_officer
from officer_direction_probe import check_saved_officer_rows, inspect_officer


def finalize_officer(attempt):
    attempt = Path(attempt)
    paths = [attempt/name for name in ('officer-survey-readback.json',
             'police-officer-actor.jsonl', 'video_frames.jsonl')]
    for path in paths:
        require(path.is_file(), 'Missing required source: ' + path.name)
    readback = json.loads(paths[0].read_text())
    with paths[1].open() as stream:
        rows = [json.loads(line) for line in stream]
    with paths[2].open() as stream:
        frames = [{'frame': json.loads(line)['carla_frame']} for line in stream]
    marker = attempt/'acquisition-provenance.json'
    synthetic = marker.is_file() and json.loads(marker.read_text()).get(
        'diagnostic_fixture') is True
    measured = check_saved_officer_rows(rows, frames, readback,
        source_kind='synthetic_native_sample' if synthetic else
                    'original_carla_actor_readback')
    measured['source_sha256'] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    measured['physical_or_legal_completion_claimed'] = False
    return measured


def run(client, carla, survey, attempt, *, reference_runner=run_reference,
        officer_capture=capture_with_officer, controller_tuning=None):
    attempt = Path(attempt)
    def acquisition(world, carla, ego, follower, sign, plan, case, path):
        require(case == 'reference', 'Officer route requires reference stop')
        readback = inspect_officer(world, survey)
        target = Path(path)/'officer-survey-readback.json'
        require(not target.exists(), 'Retain prior officer survey')
        target.write_text(json.dumps(readback, indent=2, allow_nan=False)+'\n')
        plan['police_officer_readback'] = readback
        officer = world.get_actors().find(readback['actor_id'])
        return officer_capture(world, carla, ego, follower, sign,
                               officer, plan, path)
    result = reference_runner(client, carla, survey, 'reference', attempt,
                              acquisition=acquisition,
                              controller_tuning=controller_tuning)
    measured = finalize_officer(attempt)
    report = attempt/'officer-source-measurement.json'
    require(not report.exists(), 'Retain prior officer measurement')
    report.write_text(json.dumps(measured, indent=2, allow_nan=False)+'\n')
    result['officer_source_measurement'] = report.name
    result['police_authority_verified'] = False
    result['direction_applicability_verified'] = False
    result['statutory_necessity_verified'] = False
    return result
