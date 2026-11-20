"""Executable draft Native stop with original traffic-light source retention."""
import hashlib
import json
from pathlib import Path

from device_direction_capture import acquire as capture_with_device
from device_direction_probe import check_saved_device_rows, inspect_device
from fire_lane_survey import require
from native_runner import run as run_reference


def _read_jsonl(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize_device(attempt):
    """Remeasure retained originals, preserving the statutory question."""
    attempt=Path(attempt)
    readback_path=attempt/'device-survey-readback.json'
    device_path=attempt/'traffic-control-device.jsonl'
    frame_path=attempt/'video_frames.jsonl'
    for path in (readback_path,device_path,frame_path):
        require(path.is_file(), 'Missing required source: '+path.name)
    readback=json.loads(readback_path.read_text())
    frames=[{'frame':row['carla_frame']} for row in _read_jsonl(frame_path)]
    marker=attempt/'acquisition-provenance.json'
    source_kind='original_carla_actor_readback'
    if marker.is_file() and json.loads(marker.read_text()).get('diagnostic_fixture') is True:
        source_kind='synthetic_native_sample'
    measured=check_saved_device_rows(_read_jsonl(device_path),frames,readback,
                                     source_kind=source_kind)
    measured['source_sha256']={path.name:_sha(path) for path in
                               (readback_path,device_path,frame_path)}
    measured['physical_or_legal_completion_claimed']=False
    return measured


def run(client, carla, survey, attempt,
        *, reference_runner=run_reference,
        device_capture=capture_with_device,
        controller_tuning=None):
    """Use the reference controller, retaining a distinct light-state source."""
    attempt=Path(attempt)
    def acquisition(world,carla,ego,follower,sign,plan,case,path):
        require(case=='reference', 'Device route requires reference stop')
        readback=inspect_device(world,carla,survey,plan)
        readback_path=Path(path)/'device-survey-readback.json'
        require(not readback_path.exists(), 'Retain prior device survey')
        readback_path.write_text(json.dumps(readback,indent=2,
                                           allow_nan=False)+'\n')
        plan['traffic_control_device_readback']=readback
        device=world.get_actors().find(readback['actor_id'])
        return device_capture(world,carla,ego,follower,sign,device,plan,path)
    result=reference_runner(client,carla,survey,'reference',attempt,
                            acquisition=acquisition,
                            controller_tuning=controller_tuning)
    measured=finalize_device(attempt)
    report=attempt/'device-source-measurement.json'
    require(not report.exists(), 'Retain prior device measurement')
    report.write_text(json.dumps(measured,indent=2,allow_nan=False)+'\n')
    result['device_source_measurement']=report.name
    result['direction_applicability_verified']=False
    result['statutory_necessity_verified']=False
    return result
