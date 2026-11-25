"""Saved-source diagnostic for LVMC 11.40.140 driveway-sidewalk crossing."""
import hashlib
import json

ASSIGNMENT = "training__C213851__LVMC-11-40-140__cycle_or_scooter_operator"
ASSIGNMENT_SHA = "78d0d4fca4bcfc1b7683bfcf539f2c2dcae4fd1d8b952ac037d7ee9896747bd2"
WITNESS_SHA = "0820979ea32554bc5544af938e0972d007a0ded43178948cc121ec84dedad3a4"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def measure(frame_bytes, site_bytes):
    packet, site = json.loads(frame_bytes), json.loads(site_bytes)
    require(packet["assignment_id"] == ASSIGNMENT and site["assignment_id"] == ASSIGNMENT, "assignment mismatch")
    kind = packet["source_kind"]
    require(kind in {"synthetic_native_sample", "native_saved_sample"} and site["source_kind"] == kind, "source kind mismatch")
    require(site.get('case_id') in (ASSIGNMENT+'__probe_01', ASSIGNMENT+'__probe_02'), 'exact case source missing')
    require(site.get('pedestrian_conflict_source_id'), 'pedestrian conflict source missing')
    require(site["district"] in {"business", "residence"} and site["district_source_id"], "district source missing")
    require(site["origin_kind"] in {"driveway", "alley", "building"} and site["origin_source_id"], "origin source missing")
    require(site.get('travel_direction') == 'into_driveway', 'selected entering-driveway direction missing')
    require(site["sidewalk_continuation_across_origin"] is True and site["sidewalk_continuation_source_id"], "sidewalk continuation source missing")
    require(site["sidewalk_boundary_source_id"] and site["rider_class_source_id"], "boundary or rider-class source missing")
    require(site["rider_class"] in {"bicycle", "electric_bicycle", "electric_scooter"}, "rider class outside ordinance")
    frames = packet["frames"]
    require(len(frames) >= 600, "recording shorter than 30 seconds")
    require(all(f["frame"] == i and abs(f["t_s"] - i / 20) < 1e-8 for i, f in enumerate(frames)), "noncontiguous 20 Hz frames")
    require(all(f["rider_id"] == packet["rider_id"] and f["pedestrian_id"] == packet["pedestrian_id"] for f in frames), "participant identity changed")
    require(all(f["rider_speed_mps"] >= 0 and isinstance(f["pedestrian_on_crossing"], bool) for f in frames), "motion or pedestrian source missing")
    entry = next((i for i, f in enumerate(frames) if f["rider_s_m"] >= 0), None)
    require(entry is not None and entry > 0 and frames[entry - 1]["rider_s_m"] < 0, "sidewalk entry missing")
    stop = [f["frame"] for f in frames[:entry] if f["rider_speed_mps"] <= 0.1 and f["rider_s_m"] < 0]
    ped_before_entry = [f["frame"] for f in frames[:entry] if f["pedestrian_on_crossing"]]
    ped_at_entry = frames[entry]["pedestrian_on_crossing"]
    return {"format": "c213851-saved-sidewalk-diagnostic-v1", "assignment_id": ASSIGNMENT,
            "source_kind": kind, "frame_sha256": digest(frame_bytes), "site_sha256": digest(site_bytes),
            "frame_count": len(frames), "duration_s": len(frames) / 20,
            "district": site["district"], "origin_kind": site["origin_kind"],
            "rider_class": site["rider_class"], "sidewalk_entry_frame": entry,
            "pre_entry_near_zero_frames": stop, "pedestrian_on_crossing_before_entry_frames": ped_before_entry,
            "pedestrian_on_crossing_at_entry": ped_at_entry,
            "legal_result": None,
            "unresolved": ["physical sidewalk continuation", "rider classification", "pedestrian collision necessity", "stop immediacy", "physical source validity"]}
