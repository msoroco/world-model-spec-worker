"""Measured-feedback ego/lead control for a following then lane-change scene.

Requested speed and spacing are engineering knobs, never legal conclusions.
Actual gaps and speeds must come from original Native actor state at capture.
"""
import math

def _speed(actor):
    v=actor.get_velocity()
    xyz=(float(v.x),float(v.y),float(v.z))
    if not all(math.isfinite(x) for x in xyz):raise ValueError('Nonfinite Native velocity')
    return math.sqrt(sum(x*x for x in xyz))

def _position(actor):
    p=actor.get_location();xyz=(float(p.x),float(p.y),float(p.z))
    if not all(math.isfinite(x) for x in xyz):raise ValueError('Nonfinite Native location')
    return xyz

def _control(factory,throttle,brake,steer=0):
    return factory(throttle=max(0,min(1,throttle)),brake=max(0,min(1,brake)),steer=max(-1,min(1,steer)))

class FollowingController:
    def __init__(self,control_factory,*,target_speed_mps,target_center_spacing_m,
                 lane_change_start_m,lane_change_end_m,lead_speed_mps,
                 lead_brake_start_m=None):
        values=(target_speed_mps,target_center_spacing_m,lane_change_start_m,
                lane_change_end_m,lead_speed_mps)
        if not callable(control_factory) or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            raise ValueError('Finite controller parameters required')
        if target_speed_mps<=0 or target_center_spacing_m<=0 or lead_speed_mps<=0 or lane_change_end_m<=lane_change_start_m:
            raise ValueError('Invalid engineering control phase')
        if lead_brake_start_m is not None and (type(lead_brake_start_m) not in (int,float) or not math.isfinite(lead_brake_start_m)):
            raise ValueError('Invalid lead brake trigger')
        self.factory=control_factory;self.target_speed=target_speed_mps
        self.target_spacing=target_center_spacing_m;self.lead_speed=lead_speed_mps
        self.start=lane_change_start_m;self.end=lane_change_end_m
        self.brake_start=lead_brake_start_m

    def step(self,ego,lead,*,route_origin_xyz,route_forward_xy,target_lane_center_xy):
        ex,ey,ez=_position(ego);px,py,pz=_position(lead)
        ox,oy,oz=route_origin_xyz
        fx,fy=route_forward_xy;norm=math.hypot(fx,fy)
        if norm==0 or not math.isfinite(norm):raise ValueError('Invalid route direction')
        fx,fy=fx/norm,fy/norm
        progress=(ex-ox)*fx+(ey-oy)*fy
        spacing=(px-ex)*fx+(py-ey)*fy
        ego_speed,lead_speed=_speed(ego),_speed(lead)
        if spacing<=0:raise ValueError('Lead no longer ahead on route')
        # Gap feedback slows ego before the requested center spacing is lost.
        target=min(self.target_speed,max(0.0,lead_speed+0.25*(spacing-self.target_spacing)))
        if progress>=self.end:target=min(target,lead_speed)
        error=target-ego_speed
        throttle=min(0.7,max(0.0,0.15*error));brake=min(1.0,max(0.0,-0.25*error))
        lane_change_started=progress>=self.start
        steer=0.0
        if lane_change_started and progress<self.end:
            tx,ty=target_lane_center_xy
            lateral=(tx-ex)*(-fy)+(ty-ey)*fx
            steer=max(-0.3,min(0.3,0.08*lateral))
        lead_target=0.0 if self.brake_start is not None and progress>=self.brake_start else self.lead_speed
        lead_error=lead_target-lead_speed
        lead_throttle=min(0.5,max(0.0,0.15*lead_error))
        lead_brake=min(1.0,max(0.0,-0.3*lead_error))
        ego.apply_control(_control(self.factory,throttle,brake,steer))
        lead.apply_control(_control(self.factory,lead_throttle,lead_brake))
        return {'measured_ego_speed_mps':ego_speed,'measured_lead_speed_mps':lead_speed,
                'measured_center_spacing_m':spacing,'route_progress_m':progress,
                'lane_change_started':lane_change_started,'requested_engineering_speed_mps':target,
                'ego_throttle':throttle,'ego_brake':brake,'ego_steer':steer,
                'lead_throttle':lead_throttle,'lead_brake':lead_brake}
