"""Tick-neutral Core capture of a live pedestrian as the subject actor.

The pinned generic capture assumes VehicleControl. This subclass keeps its
original map, graph, recorder and manifest setup, and records WalkerControl
without inventing throttle, steering or braking observations.
"""
from __future__ import annotations

import json
import math
import time


def _xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


class PedestrianCoreCapture:
    def __init__(self, client, walker, output, case_id):
        from pipeline_capture import PipelineCapture
        self._capture = PipelineCapture(client, walker, output, case_id)
        self.walker = walker

    def capture(self, frame, time_s):
        cap = self._capture
        if cap.closed or cap.world.get_snapshot().frame != frame:
            raise ValueError("Core pedestrian capture must join current original frame")
        transform = self.walker.get_transform()
        velocity = self.walker.get_velocity()
        position = _xyz(transform.location)
        speed = math.sqrt(sum(value * value for value in _xyz(velocity)))
        control = self.walker.get_control()
        walker_control = {
            "direction_m": _xyz(control.direction),
            "requested_speed_mps": float(control.speed),
            "source": "original_live_walker_get_control",
        }
        row = {
            "frame": frame, "time_s": time_s,
            "position": dict(zip(("x", "y", "z"), position)),
            "position_m": position, "heading_deg": float(transform.rotation.yaw),
            "speed_mps": speed, "speed_mph": speed / .44704,
            "velocity_mps": _xyz(velocity), "walker_control": walker_control,
        }
        started = time.perf_counter()
        from original_observations import observe
        observed = observe(cap.world, self.walker, frame, time_s,
                           cap.user_visibility, cap.physical_registry)
        observed["map_context"] = cap.map_context
        subject = next(item for item in observed["participants"]
                       if item["actor_id"] == self.walker.id)
        for key in ("acceleration_method", "acceleration_projection",
                    "acceleration_mps2", "forward_vector",
                    "accel_longitudinal_mps2"):
            if key in subject:
                row[key] = subject[key]
        observation_seconds = time.perf_counter() - started
        graph = cap.collector.capture(frame, None, observed_evidence=observed)
        if not graph:
            raise ValueError("Missing original pedestrian graph frame")
        waypoint = cap.map.get_waypoint(transform.location)
        weather = cap.world.get_weather()
        event = {
            "original_frame": frame, "replay_frame": frame,
            "actor_id": self.walker.id, "recording_time_s": time_s,
            "replay_simulation_time_s": graph["simulation_time"],
            "ego": {
                "position_m": position, "heading_deg": float(transform.rotation.yaw),
                "speed_mps": speed,
                "speed_provenance": "original_trace_actor_get_velocity",
                "body_vertices_m": [_xyz(point) for point in
                                    self.walker.bounding_box.get_world_vertices(transform)],
            },
            "world": {
                "weather": {key: getattr(weather, key) for key in
                            ("cloudiness", "precipitation", "precipitation_deposits",
                             "fog_density", "fog_distance", "sun_altitude_angle", "wetness")},
                "road_projection": None if waypoint is None else {
                    "road_id": waypoint.road_id, "section_id": waypoint.section_id,
                    "lane_id": waypoint.lane_id, "s_m": waypoint.s},
            },
            "original_observations": observed,
            "timing": {"observation_seconds": observation_seconds,
                       "graph_capture_seconds": graph.get("capture_seconds"),
                       "graph_extraction_seconds": graph.get("extraction_seconds")},
            "visibility": None,
            "supporting_only": {"applied_walker_control": walker_control},
        }
        cap.trace.write(json.dumps(row, allow_nan=False) + "\n")
        cap.evidence.write(json.dumps(event, allow_nan=False) + "\n")
        cap.meta["frames"] += 1
        return row

    def close(self, confirmed=True):
        self._capture.close(confirmed=confirmed)
