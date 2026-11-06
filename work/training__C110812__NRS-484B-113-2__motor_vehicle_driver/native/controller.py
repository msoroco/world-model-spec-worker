"""Observed-pose reverse route follower for an authored corner path."""
from __future__ import annotations
from dataclasses import dataclass
import math
from geometry import route

@dataclass(frozen=True)
class ReverseKnobs:
    steering_gain:float=.35
    brake_margin_m:float=.10
    target_reverse_speed_m_s:float=1.0
    def validate(self):
        if not all(math.isfinite(v) for v in vars(self).values()) or not (.1<=self.steering_gain<=.8 and 0<=self.brake_margin_m<=1 and .1<=self.target_reverse_speed_m_s<=2):
            raise ValueError('Reverse corner controller knob outside bounded range')
class ReverseController:
    def __init__(self,suffix:str,knobs:ReverseKnobs):
        if suffix not in ('condition_a','condition_b'):raise ValueError('Unknown reverse corner path')
        knobs.validate();self.suffix=suffix;self.knobs=knobs;self.path=route(suffix)
    def step(self,*,x_m:float,y_m:float,heading_rad:float,signed_forward_speed_m_s:float):
        if not all(math.isfinite(v) for v in (x_m,y_m,heading_rad,signed_forward_speed_m_s)):
            raise ValueError('Original Native pose/velocity absent')
        nearest=min(range(len(self.path)),key=lambda i:(x_m-self.path[i][0])**2+(y_m-self.path[i][1])**2)
        target=self.path[min(200,nearest+6)]
        remaining=(200-nearest)*13.817477042468104/200-self.knobs.brake_margin_m
        target_speed=min(self.knobs.target_reverse_speed_m_s,math.sqrt(max(0,2*.8*remaining)))
        observed=max(0,-signed_forward_speed_m_s);error=target_speed-observed
        throttle=max(0,min(.45,.13+.55*error)) if target_speed>.03 else 0
        brake=max(0,min(1,-.55*error)) if error<0 else 0
        if target_speed<=.03:brake=max(brake,.7)
        desired=math.radians(target[2])
        heading_error=(desired-heading_rad+math.pi)%(2*math.pi)-math.pi
        # Negative longitudinal velocity reverses the yaw response to positive steer.
        steer=max(-.45,min(.45,-self.knobs.steering_gain*heading_error))
        return {'throttle':throttle,'brake':brake,'steer':steer,'reverse':True,
                'hand_brake':target_speed<=.03 and observed<.05,
                'requested_reverse_speed_m_s':target_speed,
                'observed_signed_forward_speed_m_s':signed_forward_speed_m_s,
                'observed_center_xy_m':[x_m,y_m],'nearest_route_index':nearest,
                'target_pose_xy_yaw':[target[0],target[1],target[2]],
                'heading_error_rad':heading_error}
