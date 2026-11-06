"""Observed-pose reverse controller for a short, straight crosswalk backing path."""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ReverseKnobs:
    lateral_gain: float = .18
    brake_margin_m: float = .10
    target_reverse_speed_m_s: float = .6

    def validate(self):
        if not all(math.isfinite(v) for v in vars(self).values()) or \
           not (0<self.lateral_gain<=1 and 0<=self.brake_margin_m<=1 and
                .1<=self.target_reverse_speed_m_s<=2):
            raise ValueError('Reverse controller knob outside bounded range')


class ReverseController:
    def __init__(self, stop_x_m:float, knobs:ReverseKnobs):
        knobs.validate()
        if not -20<stop_x_m<-10:raise ValueError('Unknown reverse endpoint')
        self.stop_x_m=stop_x_m;self.knobs=knobs

    def step(self, *, x_m:float,y_m:float,heading_rad:float,
             signed_forward_speed_m_s:float):
        if not all(math.isfinite(v) for v in (x_m,y_m,heading_rad,signed_forward_speed_m_s)):
            raise ValueError('Original Native pose/velocity absent')
        if abs(heading_rad)>.4:
            raise ValueError('Unexpected heading change in straight reverse case')
        remaining=max(0.0,x_m-self.stop_x_m-self.knobs.brake_margin_m)
        target=min(self.knobs.target_reverse_speed_m_s,math.sqrt(2*.8*remaining))
        observed=max(0,-signed_forward_speed_m_s)
        error=target-observed
        throttle=max(0,min(.45,.13+.55*error)) if target>.03 else 0.0
        brake=max(0,min(1,-.55*error)) if error<0 else 0.0
        if target<=.03:brake=max(brake,.7)
        # CARLA steering sign reverses the lateral response while backing.
        steer=max(-.35,min(.35,self.knobs.lateral_gain*(y_m+1.75)))
        return {'throttle':throttle,'brake':brake,'steer':steer,
                'reverse':True,'hand_brake':target<=.03 and observed<.05,
                'requested_reverse_speed_m_s':target,
                'observed_signed_forward_speed_m_s':signed_forward_speed_m_s,
                'remaining_to_stop_m':remaining,'observed_center_xy_m':[x_m,y_m]}
