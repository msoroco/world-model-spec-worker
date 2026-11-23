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
    speed=0.0 if case["operator_motion"]=="hold_before_stop_line" and elapsed_s>=3.0 else float(site.get("engineering_target_speed_mps",3.0))
    if not 0.0 <= speed <= 8.0:
        raise ValueError("unsafe engineering speed")
    commanded=carla.Vector3D(x=dx/norm*speed,y=dy/norm*speed,z=0.0)
    bike.set_target_velocity(commanded)
    observed=bike.get_velocity()
    if not all(math.isfinite(v) for v in (observed.x,observed.y,observed.z)):
        raise ValueError("Native velocity readback unavailable")
    return {"source_kind":"original_native_control_readback","bike_id":str(bike.id),"elapsed_s":elapsed_s,"commanded_mps":[commanded.x,commanded.y,commanded.z],"observed_mps":[observed.x,observed.y,observed.z],"legal_assessment":"unresolved"}
