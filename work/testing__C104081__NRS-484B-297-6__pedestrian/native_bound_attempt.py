"""Join one original site survey, actor adapter and camera rig for Native capture.

The caller supplies a CARLA client and the pinned restore module. All source
files are retained inputs; this entrypoint does not create or infer a survey.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_actor_adapter import CarlaActorAdapter
from native_attempt import run_native_attempt
from native_camera_rig import NativeCameraRig
from native_construction import load_site_survey


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_live_site(client, survey: dict, survey_path: Path) -> str:
    """Bind a reviewed survey to the current OpenDRIVE bytes before mutation."""
    review = survey.get("reviewed_original_site")
    if not isinstance(review, dict) or not all(review.get(key) for key in
            ("reviewer", "method", "source_refs")):
        raise ValueError("original hill-crest site review is missing")
    if not isinstance(review["source_refs"], list) or not all(
            isinstance(ref, dict) and ref.get("path") and ref.get("sha256")
            for ref in review["source_refs"]):
        raise ValueError("original site review lacks source hashes")
    source_root = Path(survey_path).resolve().parent
    for ref in review["source_refs"]:
        relative = Path(ref["path"])
        if relative.is_absolute() or not relative.parts:
            raise ValueError("original site review source path must be relative")
        source = (source_root / relative).resolve()
        if not source.is_relative_to(source_root) or not source.is_file() or \
                sha(source) != ref["sha256"]:
            raise ValueError("original site review source bytes differ")
    expected = survey.get("map_opendrive_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("original hill-crest OpenDRIVE hash is missing")
    road_map = client.get_world().get_map()
    if road_map.name != survey["map_id"]:
        raise ValueError("live Native map identity differs from reviewed site")
    observed = hashlib.sha256(road_map.to_opendrive().encode("utf-8")).hexdigest()
    if observed != expected:
        raise ValueError("live Native OpenDRIVE bytes differ from reviewed site")
    return observed


def run_bound_attempt(client, carla, plan: dict, case_id: str,
                      survey_path: Path, camera_profile_path: Path,
                      traffic_plan_path: Path, output: Path, *, restore_api,
                      walking_speed_m_s: float = 1.4):
    survey_path = Path(survey_path)
    camera_profile_path = Path(camera_profile_path)
    traffic_plan_path = Path(traffic_plan_path)
    output = Path(output)
    survey_sha = sha(survey_path)
    survey = load_site_survey(survey_path, survey_sha)
    profile_sha, traffic_sha = sha(camera_profile_path), sha(traffic_plan_path)
    if survey.get("camera_profile_sha256") != profile_sha or \
            survey.get("traffic_plan_sha256") != traffic_sha:
        raise ValueError("original camera or traffic plan differs from site survey")
    profile = json.loads(camera_profile_path.read_text())
    if profile.get("cameras") != {
            "overview": [1920, 1080], "approach": [1280, 720],
            "reference_corner": [1280, 720], "driver_reference": [1280, 720]} or \
            profile.get("rate_hz") != 20:
        raise ValueError("original camera profile differs from capture contract")
    traffic = json.loads(traffic_plan_path.read_text())
    if traffic.get("actor_ids") != survey.get("traffic_actor_ids") or \
            not isinstance(traffic.get("actor_ids"), list) or not traffic["actor_ids"]:
        raise ValueError("original traffic roster differs from site survey")
    verify_live_site(client, survey, survey_path)
    world = client.get_world()
    adapter = CarlaActorAdapter(world, carla, survey)
    holder = {}

    def rig_factory(active_world):
        if active_world is not world:
            raise ValueError("original world changed before camera construction")
        staging = output.parent / (output.name + "-camera-stage")
        rig = NativeCameraRig(active_world, carla, survey_path, survey_sha, staging)
        holder["rig"] = rig
        return rig

    def reader_factory(active_world, walker, constructed, recorder):
        if "rig" not in holder:
            raise ValueError("camera rig must be owned before source reader")
        return adapter.source_reader_factory(holder["rig"])(
            active_world, walker, constructed, recorder)

    return run_native_attempt(
        client, carla, plan, case_id, survey_path, survey_sha, adapter,
        reader_factory, None, output, restore_api=restore_api,
        camera_profile_sha256=profile_sha, traffic_plan_sha256=traffic_sha,
        pedestrian_blueprint=survey["pedestrian_blueprint"],
        camera_rig_factory=rig_factory, walking_speed_m_s=walking_speed_m_s,
        core_capture_factory=_core_capture_factory)


def _core_capture_factory(client, walker, output, case_id):
    from pedestrian_core_capture import PedestrianCoreCapture
    return PedestrianCoreCapture(client, walker, output, case_id)
