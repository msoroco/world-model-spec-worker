"""Lazy CARLA-facing adapter for source-bound blind-person encounter capture.

The caller owns actor/sensor spawning and independent blindness/cue sources.
This adapter measures actor motion and camera callbacks; it does not infer legal
precautions or blindness from appearance.
"""
from __future__ import annotations

import io
import math
from queue import Empty, Queue

from PIL import Image

CAMERAS = ('front', 'left', 'right', 'rear')


class CarlaAdapter:
    def __init__(self, world, driver, person, sensors, context_reader,
                 control_factory, timeout_seconds=5.0, destroy_sensors=False):
        if set(sensors) != set(CAMERAS):
            raise ValueError('four original camera sensors required')
        settings = world.get_settings()
        if (settings.synchronous_mode is not True or
                abs(settings.fixed_delta_seconds - 0.05) > 1e-8):
            raise ValueError('Native world must be synchronous at 20 Hz')
        if driver.id == person.id:
            raise ValueError('driver and protected person actor identities must differ')
        self.world, self.driver, self.person = world, driver, person
        self.sensors, self.context_reader = sensors, context_reader
        self.control_factory, self.timeout_seconds = control_factory, timeout_seconds
        self.destroy_sensors = destroy_sensors
        self.closed = False
        self.queues = {camera: Queue() for camera in CAMERAS}
        self.listening = []
        self.last_frame = None
        self.last_time = None
        try:
            for camera in CAMERAS:
                sensor = sensors[camera]
                sensor.listen(lambda image, name=camera: self.queues[name].put(image))
                self.listening.append(sensor)
        except Exception:
            self.close()
            raise

    def tick(self):
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if (type(frame) is not int or frame != snapshot.frame or
                (self.last_frame is not None and frame != self.last_frame + 1)):
            raise ValueError('original Native world frame drift')
        time_s = snapshot.timestamp.elapsed_seconds
        if (type(time_s) not in (int, float) or not math.isfinite(time_s) or
                (self.last_time is not None and abs(time_s - self.last_time - 0.05) > 0.002)):
            raise ValueError('original Native world clock drift')
        self.last_frame, self.last_time = frame, time_s
        return frame, time_s

    def observe(self, frame):
        if frame != self.last_frame:
            raise ValueError('observation is not from current Native tick')
        driver_location = self.driver.get_transform().location
        person_location = self.person.get_transform().location
        velocity = self.driver.get_velocity()
        numbers = (driver_location.x, driver_location.y,
                   person_location.x, person_location.y,
                   velocity.x, velocity.y, velocity.z)
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in numbers):
            raise ValueError('original actor position or speed invalid')
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        center_distance = math.hypot(driver_location.x - person_location.x,
                                     driver_location.y - person_location.y)
        # Circle bounds are a conservative 2D body-gap proxy; physical contact
        # still needs the separately sourced collision observation.
        driver_extent = self.driver.bounding_box.extent
        person_extent = self.person.bounding_box.extent
        radii = (math.hypot(driver_extent.x, driver_extent.y),
                 math.hypot(person_extent.x, person_extent.y))
        if any(not math.isfinite(radius) or radius <= 0 for radius in radii):
            raise ValueError('original actor body extent invalid')
        context = self.context_reader(frame)
        if (not isinstance(context, dict) or context.get('frame') != frame or
                context.get('person_actor_id') != self.person.id or
                context.get('driver_actor_id') != self.driver.id or
                any(type(context.get(key)) is not bool for key in
                    ('person_in_path', 'person_clear', 'contact', 'precaution'))):
            raise ValueError('original encounter context identity or fields missing')
        return {'frame': frame, 'person_actor_id': self.person.id,
                'driver_actor_id': self.driver.id,
                'driver_speed_mps': speed,
                'body_gap_m': max(0.0, center_distance - sum(radii)),
                'person_in_path': context['person_in_path'],
                'person_clear': context['person_clear'],
                'contact': context['contact'],
                'precaution': context['precaution'],
                'body_gap_kind': 'circle_bound_proxy'}

    def camera_png(self, camera, frame):
        if camera not in self.queues or frame != self.last_frame:
            raise ValueError('camera request is not from current Native tick')
        try:
            image = self.queues[camera].get(timeout=self.timeout_seconds)
        except Empty as exc:
            raise ValueError('missing original camera callback: ' + camera) from exc
        if image.frame != frame or type(image.width) is not int or type(image.height) is not int or \
                image.width <= 0 or image.height <= 0:
            raise ValueError('original camera frame or dimensions differ')
        raw = bytes(image.raw_data)
        if len(raw) != image.width * image.height * 4:
            raise ValueError('original BGRA camera bytes incomplete')
        rgb = Image.frombytes('RGBA', (image.width, image.height), raw,
                              'raw', 'BGRA').convert('RGB')
        buffer = io.BytesIO()
        rgb.save(buffer, format='PNG')
        return buffer.getvalue()

    def apply_control(self, request):
        throttle, brake = request['throttle'], request['brake']
        if (not all(type(value) in (int, float) and math.isfinite(value) and
                    0 <= value <= 1 for value in (throttle, brake)) or
                throttle > 0 and brake > 0):
            raise ValueError('bounded Native vehicle control required')
        self.driver.apply_control(self.control_factory(throttle=throttle,
                                                       brake=brake))

    def emergency_stop(self):
        self.driver.apply_control(self.control_factory(throttle=0.0, brake=1.0))

    def close(self):
        if self.closed:
            return
        self.closed = True
        for sensor in self.listening:
            sensor.stop()
            if self.destroy_sensors:
                sensor.destroy()
        self.listening.clear()
        self.emergency_stop()
