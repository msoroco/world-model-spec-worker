"""Native bicycle route actuation and source-bound readback, without legal labels."""
from __future__ import annotations
import math


def command_step(bike, carla, case: dict, site: dict, elapsed_s: float) -> dict:
    if not bike.is_alive or bike.type_id != site["bike_blueprint_id"]:
        raise ValueError("bicycle Native readback failed")
    route = site["vehicle_route"]
    if len(route) < 2:
        raise ValueError("route needs two source points")
    if case["operator_motion"] not in {"hold_before_stop_line", "cross_stop_line"}:
        raise ValueError("unknown operator movement")
    p0,p1=route[0],route[1]
    dx=float(p1[0])-float(p0[0]);dy=float(p1[1])-float(p0[1])
    norm=math.hypot(dx,dy)
    if norm < 1.0:
        raise ValueError("degenerate governed route")
    line = site.get("stop_line")
    if not isinstance(line, list) or len(line) != 2:
        raise ValueError("original stop line required for route actuation")
    x0, y0 = map(float, line[0]); x1, y1 = map(float, line[1])
    lx, ly = x1-x0, y1-y0
    line_length = math.hypot(lx, ly)
    if line_length < 0.1:
        raise ValueError("degenerate original stop line")
    def side(point):
        return lx*(float(point[1])-y0)-ly*(float(point[0])-x0)
    start_side, end_side = side(p0), side(p1)
    if start_side*end_side >= 0 or abs(start_side) < 0.1:
        raise ValueError("source route does not cross governed stop line")
    transform = bike.get_transform()
    extent = float(bike.bounding_box.extent.x)
    if not math.isfinite(extent) or extent <= 0:
        raise ValueError("bicycle front-body extent unavailable")
    forward = transform.get_forward_vector()
    front = (transform.location.x + forward.x*extent,
             transform.location.y + forward.y*extent)
    signed_distance_m = side(front)/line_length * (1 if start_side > 0 else -1)
    if not math.isfinite(signed_distance_m):
        raise ValueError("bicycle front-body position unavailable")
    if signed_distance_m < -0.05 and case["operator_motion"] == "hold_before_stop_line":
        raise ValueError("bicycle crossed stop line before hold")
    margin = float(site.get("engineering_hold_margin_m", 2.0))
    if not 0.5 <= margin <= 5.0:
        raise ValueError("unsafe engineering stop-line margin")
    speed=0.0 if case["operator_motion"]=="hold_before_stop_line" and signed_distance_m <= margin else float(site.get("engineering_target_speed_mps",3.0))
    if not 0.0 <= speed <= 8.0:
        raise ValueError("unsafe engineering speed")
    commanded=carla.Vector3D(x=dx/norm*speed,y=dy/norm*speed,z=0.0)
    bike.set_target_velocity(commanded)
    observed=bike.get_velocity()
    if not all(math.isfinite(v) for v in (observed.x,observed.y,observed.z)):
        raise ValueError("Native velocity readback unavailable")
    return {"source_kind":"original_native_control_readback","bike_id":str(bike.id),"elapsed_s":elapsed_s,"front_to_stop_line_m":signed_distance_m,"engineering_hold_margin_m":margin,"commanded_mps":[commanded.x,commanded.y,commanded.z],"observed_mps":[observed.x,observed.y,observed.z],"legal_assessment":"unresolved"}
