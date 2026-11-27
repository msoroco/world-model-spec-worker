"""Lazy CARLA bridge for one source-certified electric scooter and four cameras."""
import hashlib
import io
import math
from queue import Queue
from package_spec import CAMERA_NAMES
from scooter_785 import SOURCE_ROLES,need


class CarlaScooterAdapter:
    native_attested=True

    def __init__(self,host,port,site,case,profile):
        import carla
        self.carla=carla
        self.client=carla.Client(str(host),int(port))
        self.client.set_timeout(20)
        self.world=self.client.get_world()
        self.settings=self.world.get_settings()
        self.site,self.scene,self.case,self.profile=site,site['scene'],case,profile
        self.owned=[]
        self.queues={}
        self.restoration_verified=False

    def configure(self):
        native_map=self.world.get_map()
        need(native_map.name==self.site['map_name'] and
             hashlib.sha256(native_map.to_opendrive().encode()).hexdigest()==self.site['map_sha256'],
             'reviewed original Native map differs')
        settings=self.world.get_settings()
        settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05
        self.world.apply_settings(settings)

    def spawn(self):
        c=self.carla
        route=self.scene['ego_route_xy']
        bp=self.world.get_blueprint_library().find(self.site['scooter_blueprint_id'])
        need(bp.id==self.site['scooter_blueprint_id'],'reviewed scooter asset missing')
        yaw=math.degrees(math.atan2(route[1][1]-route[0][1],route[1][0]-route[0][0]))
        z=float(self.site['spawn_z_m'])+float(self.profile.get('spawn_z_adjust_m',0))
        need(abs(float(self.profile.get('spawn_z_adjust_m',0)))<=.2,
             'scooter spawn engineering adjustment exceeds surveyed tolerance')
        self.ego=self.world.try_spawn_actor(bp,c.Transform(c.Location(x=route[0][0],y=route[0][1],z=z),
                                             c.Rotation(yaw=yaw)))
        need(self.ego is not None and self.ego.is_alive and self.ego.type_id==bp.id,
             'source-identified original scooter spawn/readback failed')
        self.owned.append(self.ego)
        offsets={'overview':(-10,0,20),'approach':(-6,3,5),
                 'reference_corner':(2,5,6),'driver_reference':(0,0,2)}
        for index,name in enumerate(CAMERA_NAMES):
            camera_bp=self.world.get_blueprint_library().find('sensor.camera.rgb')
            width,height=((1920,1080) if index==0 else (1280,720))
            camera_bp.set_attribute('image_size_x',str(width))
            camera_bp.set_attribute('image_size_y',str(height))
            camera_bp.set_attribute('sensor_tick','0.05')
            offset=offsets[name]
            sensor=self.world.spawn_actor(camera_bp,c.Transform(c.Location(x=offset[0],y=offset[1],z=offset[2])),attach_to=self.ego)
            queue=Queue()
            sensor.listen(queue.put)
            self.owned.append(sensor)
            self.queues[name]=queue

    def control(self):
        route=self.scene['ego_route_xy']
        direction=(route[-1][0]-route[0][0],route[-1][1]-route[0][1])
        length=math.hypot(*direction)
        need(length>=250,'reviewed scooter route too short')
        speed=self.case.speed_mph*.44704
        need(speed>0,'scooter requested speed missing')
        self.ego.set_target_velocity(self.carla.Vector3D(x=speed*direction[0]/length,
                                                          y=speed*direction[1]/length,z=0))

    def tick(self):
        self.control()
        frame=self.world.tick()
        snapshot=self.world.get_snapshot()
        need(snapshot.frame==frame,'Native scooter frame identity differs')
        return frame,snapshot.timestamp.elapsed_seconds

    def read(self,frame,time_s):
        actor=self.ego
        location=actor.get_location()
        velocity=actor.get_velocity()
        box=actor.bounding_box
        transform=actor.get_transform()
        corners=[]
        for sx,sy in ((-1,-1),(-1,1),(1,1),(1,-1)):
            local=self.carla.Location(x=sx*box.extent.x,y=sy*box.extent.y,z=0)
            point=transform.transform(local)
            corners.append([point.x,point.y])
        return {'frame':frame,'time_s':time_s,'native_actor_id':str(actor.id),
                'device_id':self.scene['device']['device_id'],
                'body_corners_xy':corners,'position_xyz_m':[location.x,location.y,location.z],
                'heading_deg':transform.rotation.yaw,
                'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
                **{role+'_source_sha256':self.scene[role+'_source_sha256'] for role in SOURCE_ROLES}}

    def pixels(self,frame):
        from PIL import Image
        out={}
        for name in CAMERA_NAMES:
            image=self.queues[name].get(timeout=10)
            need(image.frame==frame,'original scooter camera frame differs: '+name)
            bitmap=Image.frombytes('RGBA',(image.width,image.height),bytes(image.raw_data),'raw','BGRA')
            buffer=io.BytesIO()
            bitmap.convert('RGB').save(buffer,format='PNG')
            out[name]={'frame':frame,'png':buffer.getvalue()}
        return out

    def cleanup(self):
        try:
            if hasattr(self,'ego'):
                self.ego.set_target_velocity(self.carla.Vector3D(x=0,y=0,z=0))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass
            self.world.apply_settings(self.settings)
            need(self.world.get_settings().synchronous_mode==self.settings.synchronous_mode,
                 'Native world restoration failed')
            self.restoration_verified=True
