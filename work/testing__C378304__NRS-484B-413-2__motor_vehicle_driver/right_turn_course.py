"""Source-trace checks for the C378304 right-turn course change.

The first sustained clockwise heading change defines onset. This is a sampled
measurement, not a claim about the exact continuous-time crossing instant.
"""

import math


def _angle_delta(degrees, reference):
    return (degrees - reference + 180.0) % 360.0 - 180.0


def measure_right_turn(rows, context):
    if len(rows) < 7:
        raise ValueError("Right-turn trace needs approach, turn and exit samples")
    headings = []
    for row in rows:
        heading = row.get("ego_heading_deg")
        if isinstance(heading, bool) or not isinstance(heading, (int, float)) or not math.isfinite(heading):
            raise ValueError("Missing finite Native heading")
        headings.append(float(heading))
    baseline = headings[0]
    if any(abs(_angle_delta(h, baseline)) > 1.0 for h in headings[:3]):
        raise ValueError("No stable direct-course approach")
    onset_index = next((i for i, h in enumerate(headings[3:], 3)
                        if _angle_delta(h, baseline) <= -3.0), None)
    if onset_index is None or onset_index + 2 >= len(rows):
        raise ValueError("No sustained measured right-turn onset")
    angles = [_angle_delta(h, baseline) for h in headings]
    if (angles[onset_index + 1] >= angles[onset_index] + 1.0
            or angles[onset_index + 2] >= angles[onset_index + 1] + 1.0
            or min(angles[onset_index:]) > -45.0):
        raise ValueError("Heading does not sustain a right turn")
    approach = (context["approach_road_id"], context["approach_lane_id"])
    outgoing = (context["outgoing_road_id"], context["outgoing_lane_id"])
    if approach == outgoing:
        raise ValueError("Outgoing lane does not differ from approach")
    lanes = [(row.get("native_road_id"), row.get("native_lane_id")) for row in rows]
    if any(lane != approach for lane in lanes[:onset_index + 1]):
        raise ValueError("Turn onset is outside the approach lane")
    exit_index = next((i for i, lane in enumerate(lanes[onset_index + 1:], onset_index + 1)
                       if lane == outgoing), None)
    if exit_index is None or any(lane != outgoing for lane in lanes[exit_index:]):
        raise ValueError("Trace never settles on the outgoing lane")
    return {"turn_onset_frame": rows[onset_index]["frame"],
            "turn_onset_index": onset_index,
            "outgoing_entry_frame": rows[exit_index]["frame"],
            "heading_change_deg": min(angles[onset_index:]),
            "method": "first sampled >=3 degree clockwise departure from stable approach, sustained for two frames and followed by outgoing-lane entry"}
