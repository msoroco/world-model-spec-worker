"""Walker telemetry adapter for the pinned original scene graph capture.

PipelineCapture owns the native recorder, map facts, graph collector and trace.
This override records WalkerControl explicitly instead of reading vehicle-only
throttle, brake and gear fields from a pedestrian actor.
"""
from __future__ import annotations

import json
import math
import time

from pipeline_capture import PipelineCapture, xyz


class WalkerPipelineCapture(PipelineCapture):
    def capture(self, frame, time_s, walker_sample):
        if self.closed or self.world.get_snapshot().frame != frame:
            raise RuntimeError("walker graph capture must observe the current original frame")
        if walker_sample["frame"] != frame or abs(walker_sample["time_s"]-time_s) > 1e-6:
            raise ValueError("walker body and graph frame identity differ")
        transform = self.ego.get_transform()
        velocity = self.ego.get_velocity()
        control = self.ego.get_control()
        speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
        position = xyz(transform.location)
        walker_control = {"direction_xyz": xyz(control.direction),
                          "requested_speed_mps": float(control.speed),
                          "jump": bool(control.jump)}
        row = {"frame": frame, "time_s": time_s,
               "actor_id": walker_sample["actor_id"],
               "position": dict(zip(("x", "y", "z"), position)),
               "position_m": position, "heading_deg": transform.rotation.yaw,
               "speed_mps": speed, "speed_mph": speed/.44704,
               "velocity_mps": xyz(velocity), "control": {},
               "walker_control": walker_control}
        from original_observations import observe
        started = time.perf_counter()
        observations = observe(self.world, self.ego, frame, time_s,
                               self.user_visibility, self.physical_registry)
        observations["map_context"] = self.map_context
        subject = next((item for item in observations["participants"]
                        if item["actor_id"] == self.ego.id), None)
        if subject is None:
            raise RuntimeError("original participant inventory omits walker")
        for key in ("accel_longitudinal_mps2", "acceleration_method",
                    "acceleration_projection", "acceleration_mps2",
                    "forward_vector"):
            if key in subject:
                row[key] = subject[key]
        observation_seconds = time.perf_counter()-started
        graph = self.collector.capture(frame, None, observed_evidence=observations)
        if not graph:
            raise RuntimeError("missing original walker adapter graph frame")
        waypoint = self.map.get_waypoint(transform.location)
        weather = self.world.get_weather()
        event = {"original_frame": frame, "replay_frame": frame,
                 "actor_id": self.ego.id, "recording_time_s": time_s,
                 "replay_simulation_time_s": graph["simulation_time"],
                 "ego": {"position_m": position,
                         "heading_deg": transform.rotation.yaw,
                         "speed_mps": speed,
                         "speed_provenance": "original_trace_actor_get_velocity",
                         "body_vertices_m": [xyz(vertex) for vertex in
                             self.ego.bounding_box.get_world_vertices(transform)]},
                 "world": {"weather": {key: getattr(weather, key) for key in
                     ("cloudiness", "precipitation", "precipitation_deposits",
                      "fog_density", "fog_distance", "sun_altitude_angle", "wetness")},
                     "road_projection": None if waypoint is None else {
                         "road_id": waypoint.road_id,
                         "section_id": waypoint.section_id,
                         "lane_id": waypoint.lane_id, "s_m": waypoint.s}},
                 "original_observations": observations,
                 "timing": {"observation_seconds": observation_seconds,
                            "graph_capture_seconds": graph.get("capture_seconds"),
                            "graph_extraction_seconds": graph.get("extraction_seconds")},
                 "supporting_only": {"applied_walker_control": walker_control}}
        self.trace.write(json.dumps(row, allow_nan=False)+"\n")
        self.evidence.write(json.dumps(event, allow_nan=False)+"\n")
        self.meta["frames"] += 1
        return row
