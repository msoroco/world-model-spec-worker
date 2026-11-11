"""Write same-frame Native velocity and trace rows after four camera frames join.

Call record_sample only after all four sensor frames for the current world tick
have been received. The caller owns FrameMap and closes all streams on exit.
"""

import json
import math


def record_sample(frame_map, motion_stream, trace_stream, subject, snapshot):
    frame = snapshot.frame
    time = snapshot.timestamp.elapsed_seconds
    velocity = subject.get_velocity()
    transform = subject.get_transform()
    position = transform.location
    xyz = [float(velocity.x), float(velocity.y), float(velocity.z)]
    heading = float(transform.rotation.yaw)
    if not all(math.isfinite(v) for v in (*xyz, float(position.x), float(position.y), float(position.z), float(time), heading)):
        raise ValueError("Nonfinite original Native sample")
    speed = math.sqrt(sum(value * value for value in xyz))
    mapping = frame_map.append(frame, time)
    motion = {"frame": frame, "time_s": time,
              "subject_actor_id": subject.id,
              "speed_source": "actor.get_velocity",
              "velocity_mps": xyz,
              "speed_mps": speed}
    trace = {"frame": frame, "time_s": time,
             "position_m": [float(position.x), float(position.y), float(position.z)],
             "velocity_mps": xyz, "speed_mps": speed,
             "heading_deg": heading}
    motion_stream.write(json.dumps(motion, allow_nan=False) + "\n")
    trace_stream.write(json.dumps(trace, allow_nan=False) + "\n")
    return {"video_frame": mapping["video_frame"], "motion": motion, "trace": trace}
