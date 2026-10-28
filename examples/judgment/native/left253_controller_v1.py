"""Observed-state engineering choreography; no legal hazard/yield classifier.

Distances, deceleration and event margins below control a physical construction.
They never resolve immediate hazard, yielding, intent or lawful progression.
"""
import math
from dataclasses import dataclass


def clamp(v,a,b):return max(a,min(b,v))


@dataclass
class SpeedController:
    integral:float=0.
    def step(self,speed,target):
        assert all(math.isfinite(v) for v in [speed,target]) and speed>=0 and target>=0
        e=target-speed;trial=clamp(self.integral+.05*e,-3,3)
        raw=.12+.6*e+.15*trial
        if not ((raw>1 and e>0) or (raw< -1 and e<0)):self.integral=trial
        raw=.12+.6*e+.15*self.integral
        stopped=target<.02
        return {'throttle':0. if stopped else clamp(raw,0,1),'brake':.7 if stopped else clamp(-raw,0,1),'hand_brake':stopped and speed<.05,'requested_speed_mps':target,'observed_speed_mps':speed,'integral_error':self.integral}


class PathController:
    def __init__(self,points,max_steer_deg,wheelbase_m):
        self.points=[tuple(p) for p in points];self.cumulative=[0.]
        assert max_steer_deg>0 and wheelbase_m>0
        self.max_steer=math.radians(max_steer_deg);self.wheelbase=wheelbase_m
        for a,b in zip(points,points[1:]):self.cumulative.append(self.cumulative[-1]+math.dist(a,b))
        self.last=0;self.speed=SpeedController()
    def locate(self,state):
        p=state['position_m'][:2]
        # Bounded monotonic tracking from actual pose. No actor teleportation.
        candidates=range(max(0,self.last-5),min(len(self.points),self.last+180))
        index=min(candidates,key=lambda i:math.dist(p,self.points[i]))
        self.last=max(self.last,index)
        return index,math.dist(p,self.points[index])
    def step(self,state,target,stop_station=None):
        index,error=self.locate(state);station=self.cumulative[index]
        if stop_station is not None:target=min(target,math.sqrt(2*1.6*max(0,stop_station-station-.3)))
        request=self.speed.step(state['speed_mps'],target)
        lookahead=max(2.5,min(5.,1.1*state['speed_mps']))
        aim=index
        while aim<len(self.points)-1 and self.cumulative[aim]<station+lookahead:aim+=1
        dx=self.points[aim][0]-state['position_m'][0];dy=self.points[aim][1]-state['position_m'][1]
        # Native heading is supplied as radians, derived from actual native pose.
        alpha=math.atan2(dy,dx)-state['yaw_rad']
        alpha=math.atan2(math.sin(alpha),math.cos(alpha))
        steer=math.atan2(2*self.wheelbase*math.sin(alpha),max(.01,math.hypot(dx,dy)))/self.max_steer
        request.update(steer=clamp(steer,-.7,.7),path_station_m=station,path_error_m=error,aim_native_xy=self.points[aim],actual_precontrol_native_state=state)
        return request


class InteractionController:
    def __init__(self,paths,vehicle_parameters,opposing_request_mps=6.,duration_s=30.):
        self.controllers={role:PathController(points,vehicle_parameters[role]['max_steer_deg'],vehicle_parameters[role]['wheelbase_m']) for role,points in paths.items()}
        self.phase='approach';self.phase_history=[];self.opposing_speed=opposing_request_mps;self.duration=duration_s
    def step(self,frame,time_s,states):
        assert set(states)==set(self.controllers)
        ego=states['ego'];initial=states['initial_opposing']
        index,_=self.controllers['ego'].locate(ego);station=self.controllers['ego'].cumulative[index]
        stop_station=48.2
        # All transition inputs are native body/velocity history, never a label.
        full_ego=all(-7<v[0]<7 and -7<v[1]<7 for v in ego['body_vertices_native_m'])
        initial_cleared=max(v[0] for v in initial['body_vertices_native_m'])< -9.
        if self.phase=='approach' and full_ego and ego['speed_mps']<.15:
            self.phase='wait';self.phase_history.append({'frame':frame,'time_s':time_s,'phase':'wait','observed_full_body_inside':True})
        if self.phase=='wait' and initial_cleared:
            self.phase='turn';self.phase_history.append({'frame':frame,'time_s':time_s,'phase':'turn','initial_rear_x_m':max(v[0] for v in initial['body_vertices_native_m'])})
        ego_cleared=max(v[1] for v in ego['body_vertices_native_m'])< -7.
        if self.phase=='turn' and ego_cleared:
            self.phase='departure';self.phase_history.append({'frame':frame,'time_s':time_s,'phase':'departure'})
        requests={}
        for role,s in states.items():
            target=0. if time_s<1. or time_s>=self.duration-5 else (6. if role=='ego' else self.opposing_speed)
            controller=self.controllers[role];end=controller.cumulative[-1]
            stop=end-4.
            if role=='ego':
                if self.phase in ('approach','wait'):stop=stop_station
                if self.phase=='wait':target=0.
                if self.phase=='turn':target=min(target,3.5)
            elif role!='initial_opposing':
                # While ego is physically turning, request a geometric hold at
                # x=12m. The event policy is engineering choreography, not duty.
                front=min(v[0] for v in s['body_vertices_native_m'])
                if self.phase=='turn' and front>9.:
                    idx,_=controller.locate(s);current=controller.cumulative[idx]
                    stop=min(stop,current+max(0,front-12.))
                    target=0.  # observed turn triggers explicit engineering braking/hold
                predecessors=[v for k,v in states.items() if k!='ego' and k!=role and v['position_m'][0]<s['position_m'][0]]
                if predecessors:
                    nearest=max(predecessors,key=lambda v:v['position_m'][0])
                    clear=min(v[0] for v in s['body_vertices_native_m'])-max(v[0] for v in nearest['body_vertices_native_m'])
                    target=min(target,max(0,nearest['speed_mps']+.6*(clear-8.)))
            requests[role]=controller.step(s,target,stop)
            requests[role]['engineering_phase']=self.phase
        return requests
