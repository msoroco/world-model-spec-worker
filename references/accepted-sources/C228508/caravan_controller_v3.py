"""Flat-road observed-predecessor feedback; physical requests, no legal standard."""
from dataclasses import dataclass
import math

DT = .05

def clamp(value, lower, upper):
    return max(lower, min(upper, value))

def gap(follower, predecessor):
    """Signed clear gap along the flat straight +X route; all eight box vertices."""
    a, b = follower['body_vertices_native_m'], predecessor['body_vertices_native_m']
    if len(a) != 8 or len(b) != 8:
        raise ValueError('Complete native bodies required')
    return min(p[0] for p in b)-max(p[0] for p in a)

def leader_target(time_s, cruise_mps, duration_s):
    # The duration contract is prospective; all actual responses must be retained.
    if duration_s not in (30,35,40,45) or cruise_mps not in (6,9):
        raise ValueError('Unassessed physical schedule')
    brake_s = duration_s-8
    if time_s < 2 or time_s >= brake_s:
        return 0.
    if 14 <= time_s < 19:
        return cruise_mps/2
    return min(cruise_mps, max(0.,time_s-2)*1.5)

@dataclass
class SpeedController:
    integral: float = 0.

    def step(self, observed_speed, target, feedforward=0.):
        if not all(math.isfinite(x) for x in (observed_speed,target,feedforward)):
            raise ValueError('Nonfinite observed control input')
        error=target-observed_speed
        trial=clamp(self.integral+DT*error,-3.,3.)
        output=feedforward+.6*error+.15*trial
        if not ((output>1 and error>0) or (output< -1 and error<0)):
            self.integral=trial
        output=feedforward+.6*error+.15*self.integral
        stopped=target<.02
        return {'throttle':0. if stopped else clamp(output,0.,1.),
                'brake':.7 if stopped else clamp(-output,0.,1.),
                'hand_brake':stopped and observed_speed<.05,
                'requested_speed_mps':target,
                'observed_speed_mps':observed_speed,
                'integral_error':self.integral}

@dataclass
class FollowerController:
    target_gap_m: float
    cruise_mps: float
    last_frame: int = -1
    speed: SpeedController = None

    def __post_init__(self):
        if self.target_gap_m not in (30,60,90) or self.cruise_mps not in (6,9):
            raise ValueError('Unassessed physical proposal')
        self.speed=SpeedController()

    def step(self, frame, elapsed_s, follower, predecessor):
        if frame<=self.last_frame or follower['actor_id']==predecessor['actor_id']:
            raise ValueError('Distinct predecessor and fresh observed frame required')
        measured=gap(follower,predecessor)
        vs=follower['velocity_mps'][0]
        vp=predecessor['velocity_mps'][0]
        # Remove extra relative-velocity gain that amplified predecessor speed ripple.
        target=clamp(vp+.65*(measured-self.target_gap_m),0.,self.cruise_mps+3)
        pc=predecessor['applied_control']
        # Retained v1 rear-member oscillation: predecessor actuator feedforward
        # cascaded drivetrain transients. Use observed predecessor motion only;
        # keep its actual actuation in the saved input record.
        request=self.speed.step(vs,target,.12 if target>.02 else 0.)
        if abs(vp)<.1 and measured-self.target_gap_m<=.3:
            request.update(throttle=0.,brake=.7,hand_brake=abs(vs)<.05)
        request['actual_controller_inputs']={'native_frame':frame,'elapsed_s':elapsed_s,
            'follower':follower,'predecessor':predecessor,
            'observed_clear_gap_m':measured,'requested_clear_gap_m':self.target_gap_m}
        self.last_frame=frame
        return request
