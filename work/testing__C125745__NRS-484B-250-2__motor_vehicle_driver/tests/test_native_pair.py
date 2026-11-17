import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_pair import construct_pair, step_pair
from test_median_route_control import scene


class Actor:
    def __init__(self,x,y,yaw=0,speed=0):
        self.pose=NS(location=NS(x=x,y=y),rotation=NS(yaw=yaw))
        self.velocity=NS(x=speed,y=0,z=0)
        self.commands=[]
        self.destroyed=False
    def get_transform(self):return self.pose
    def get_velocity(self):return self.velocity
    def apply_control(self,command):self.commands.append(command)
    def destroy(self):self.destroyed=True


class Actors(list):
    def filter(self,pattern):return self


class World:
    def __init__(self,actors,fail_second=False):
        self.sign=NS(id=17,trigger_volume=NS(contains=lambda point,transform:True),
                     get_transform=lambda:None)
        self.actors=actors
        self.fail_second=fail_second
        self.calls=[]
    def get_actors(self):return Actors([self.sign])
    def try_spawn_actor(self,blueprint,transform):
        self.calls.append((blueprint,transform))
        if self.fail_second and len(self.calls)==2:return None
        return self.actors[len(self.calls)-1]


class NativePairTests(unittest.TestCase):
    def test_spawns_both_and_destroys_even_on_capture_error(self):
        ego,other=Actor(0,0),Actor(15,-15)
        world=World([ego,other])
        waypoint=NS(transform=NS(location='ego-approach'))
        with self.assertRaisesRegex(RuntimeError,'capture'):
            with construct_pair(world,scene(),'ego-blueprint','other-blueprint',
                                'ego-transform','other-transform',waypoint) as (a,b,sign):
                self.assertIs(a,ego);self.assertIs(b,other);self.assertEqual(sign.id,17)
                raise RuntimeError('capture failed')
        self.assertEqual(world.calls,[('ego-blueprint','ego-transform'),
                                      ('other-blueprint','other-transform')])
        self.assertTrue(ego.destroyed and other.destroyed)

    def test_failed_second_spawn_cleans_first(self):
        ego=Actor(0,0)
        world=World([ego],fail_second=True)
        waypoint=NS(transform=NS(location='ego-approach'))
        with self.assertRaisesRegex(ValueError,'other Native spawn failed'):
            with construct_pair(world,scene(),'ego','other','et','ot',waypoint):pass
        self.assertTrue(ego.destroyed)

    def test_wrong_sign_rejected_before_spawning(self):
        world=World([Actor(0,0),Actor(15,-15)])
        world.sign.id=99
        waypoint=NS(transform=NS(location='ego-approach'))
        with self.assertRaisesRegex(ValueError,'sign ID'):
            with construct_pair(world,scene(),'ego','other','et','ot',waypoint):pass
        self.assertEqual(world.calls,[])

    def test_stop_wait_and_release_apply_native_commands(self):
        ego,other=Actor(8,0,speed=.05),Actor(15,-15,speed=0)
        carla=NS(VehicleControl=lambda:NS())
        progress,stopped,commands=step_pair(carla,ego,other,scene(),
                                            {'ego':1,'other':1},False,False,False)
        self.assertTrue(stopped)
        self.assertEqual(commands['ego']['brake'],1)
        self.assertEqual(commands['other']['brake'],1)
        progress,stopped,commands=step_pair(carla,ego,other,scene(),
                                            progress,stopped,True,True)
        self.assertGreater(commands['ego']['throttle'],0)
        self.assertGreater(commands['other']['throttle'],0)
        self.assertEqual(len(ego.commands),2)
        self.assertEqual(len(other.commands),2)

    def test_selected_release_frames_control_other_independently(self):
        # These values are the exact first-case primary and fallback1 settings.
        primary=json.loads((ROOT/'construction.json').read_text())
        fallback=json.loads((ROOT/'fallback1-construction.json').read_text())
        release_frames=[]
        for construction in (primary,fallback):
            configs=[item for item in construction['files'] if item['path'].endswith('config.json')]
            self.assertEqual(len(configs),1)
            release_frames.append(json.loads(configs[0]['content'])['other_release_frame'])
        self.assertEqual(release_frames,[40,32])

        carla=NS(VehicleControl=lambda:NS())
        ego_traces=[]
        for release_frame in release_frames:
            ego,other=Actor(8,0,speed=.05),Actor(15,-15,speed=0)
            progress={'ego':1,'other':1}
            stopped=False
            trace=[]
            for frame in range(50):
                progress,stopped,commands=step_pair(
                    carla,ego,other,scene(),progress,stopped,False,
                    frame>=release_frame)
                trace.append(commands)
            self.assertEqual(len(ego.commands),50)
            self.assertEqual(len(other.commands),50)
            self.assertEqual([i for i,c in enumerate(trace)
                              if c['other']['throttle']>0],
                             list(range(release_frame,50)))
            self.assertTrue(all(c['other']['brake']==1 for c in trace[:release_frame]))
            self.assertTrue(all(c['other']['brake']==0 for c in trace[release_frame:]))
            ego_traces.append([c['ego'] for c in trace])
        self.assertEqual(ego_traces[0],ego_traces[1])

    def test_canonical_cases_bind_exact_release_and_clear_hold_controls(self):
        proposal=json.loads((ROOT/'proposals/cases.json').read_text())
        bindings=json.loads((ROOT/'proposals/bindings.json').read_text())
        self.assertIn('ego_hold_after_clear_frames',
                      {item['name'] for item in bindings['variable_parameters']})
        constructions=('construction.json','second-construction.json',
                       'third-construction.json','fourth-construction.json')
        cases={item['case_id']:item for item in proposal['cases']}
        for name in constructions:
            construction=json.loads((ROOT/name).read_text())
            config=json.loads(next(item['content'] for item in construction['files']
                                   if item['path']=='config.json'))
            case=cases[construction['case_id']]
            values=case['variable_assignments']
            self.assertEqual(values['other_release_frame']['value'],
                             config['other_release_frame'])
            self.assertEqual(values['ego_hold_after_clear_frames']['value'],
                             config.get('ego_hold_after_clear_frames',0))
        separated=cases[next(key for key in cases if key.endswith('__stop_ego_left_separated'))]
        self.assertEqual(separated['deliberate_differences'],
                         ['ego_hold_after_clear_frames'])
        self.assertEqual(separated['probe']['primary_variable'],
                         'ego_hold_after_clear_frames')

if __name__=='__main__':unittest.main()
