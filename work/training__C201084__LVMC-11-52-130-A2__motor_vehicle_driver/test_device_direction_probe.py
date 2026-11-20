"""CPU checks for source retention in the traffic-control-device route."""
import unittest
from types import SimpleNamespace

from device_direction_probe import (check_saved_device_rows, inspect_device,
                                    sample_device)
from device_direction_capture import acquire
import tempfile
from pathlib import Path


def location(x, y, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


class DeviceDirectionTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(
            id=203, type_id='traffic.traffic_light',
            get_transform=lambda:SimpleNamespace(location=location(22,1)),
            get_state=lambda:'Red')
        world = SimpleNamespace(
            get_actors=lambda:SimpleNamespace(find=lambda ident:
                actor if ident == 203 else None),
            get_map=lambda:SimpleNamespace(get_waypoint=lambda *args, **kwargs:
                SimpleNamespace(road_id=17,lane_id=-1)))
        carla = SimpleNamespace(Location=lambda **kw:SimpleNamespace(**kw),
                                LaneType=SimpleNamespace(Driving=1))
        survey = {'traffic_control_device':{'actor_id':203,
                                             'position_xy_m':[22,1]}}
        plan = {'fixed_context':{'road_id':17}}
        return actor,world,carla,survey,plan

    def test_survey_and_full_clock_retained_source(self):
        actor,world,carla,survey,plan=self.fixture()
        readback=inspect_device(world,carla,survey,plan)
        self.assertFalse(readback['direction_applicability_verified'])
        frames=[{'frame':i} for i in range(100,700)]
        rows=[dict(sample_device(actor,readback,row['frame']),video_frame=i)
              for i,row in enumerate(frames)]
        result=check_saved_device_rows(rows,frames,readback)
        self.assertEqual(result['source_frames'],600)
        self.assertEqual(result['state_counts']['Red'],600)
        self.assertFalse(result['statutory_necessity_verified'])

    def test_missing_device_changed_road_and_bad_source_are_rejected(self):
        actor,world,carla,survey,plan=self.fixture()
        survey['traffic_control_device']['actor_id']=204
        with self.assertRaisesRegex(ValueError,'actor missing'):
            inspect_device(world,carla,survey,plan)
        survey['traffic_control_device']['actor_id']=203
        with self.assertRaisesRegex(ValueError,'not on surveyed road'):
            inspect_device(world,carla,survey,{'fixed_context':{'road_id':18}})
        readback=inspect_device(world,carla,survey,plan)
        frames=[{'frame':i} for i in range(600)]
        rows=[dict(sample_device(actor,readback,i),video_frame=i)
              for i in range(600)]
        rows[5]['direction_applicability_verified']=True
        with self.assertRaisesRegex(ValueError,'overclaims'):
            check_saved_device_rows(rows,frames,readback)
        rows[5]['direction_applicability_verified']=False
        rows[5]['device_actor_id']=999
        with self.assertRaisesRegex(ValueError,'source differs'):
            check_saved_device_rows(rows,frames,readback)

    def test_native_capture_sidecar_joins_all_600_frames(self):
        actor,world,carla,survey,plan=self.fixture()
        readback=inspect_device(world,carla,survey,plan)
        plan.update(capture_hz=20,capture_frames=600,
                    camera_names=['overview','approach','reference_corner',
                                  'driver_reference'],
                    traffic_control_device_readback=readback)
        with tempfile.TemporaryDirectory() as tmp:
            attempt=Path(tmp)
            def base_acquire(world,carla,ego,follower,sign,plan,case,path,
                             *,frame_map_factory):
                self.assertEqual(case,'reference')
                frames=frame_map_factory(path/'video_frames.jsonl')
                for i in range(600):
                    frames.append(i+100,i*0.05)
                frames.close()
                return {'source_frames':600}
            result=acquire(world,carla,None,None,None,actor,plan,attempt,
                           base_acquire=base_acquire)
            self.assertEqual(result['device_measurement']['source_frames'],600)
            self.assertEqual(result['device_measurement']['state_counts']['Red'],600)
            self.assertFalse(result['direction_applicability_verified'])
            with (attempt/'traffic-control-device.jsonl').open() as stream:
                self.assertEqual(sum(1 for _ in stream),600)


if __name__ == '__main__':
    unittest.main()
