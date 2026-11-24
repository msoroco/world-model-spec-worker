"""Join original Native officer, ego, camera and PipelineCapture sources."""

from pathlib import Path
from queue import Empty, Queue

from officer_camera import CAMERAS, FourCameraEncoder
from officer_capture_sources import OfficerSourceWriter
from officer_direction import apply_direction


class NativeOfficerCapture:
    """One synchronized capture, with no inferred police or traffic-control labels."""

    def __init__(self, world, client, root, case_id, actors, context,
                 camera_blueprints, camera_mounts, required_atoms, direction_adapter,
                 frames, sizes=None, sensor_timeout_s=10,
                 encoder_factory=FourCameraEncoder,
                 writer_factory=OfficerSourceWriter, capture_factory=None):
        if (type(frames) is not int or frames < 3 or
                not isinstance(actors, dict) or "ego" not in actors or
                set(camera_blueprints) != set(CAMERAS) or
                set(camera_mounts) != set(CAMERAS) or
                context.get("case_id") != case_id or
                context.get("officer_actor_id") != getattr(actors.get("officer"), "id", None) or
                not isinstance(required_atoms, (list, tuple))):
            raise ValueError("Incomplete exact officer Native capture contract")
        self.world, self.client, self.root = world, client, Path(root)
        self.case_id, self.actors, self.context = case_id, actors, context
        self.camera_blueprints, self.camera_mounts = camera_blueprints, camera_mounts
        self.required_atoms, self.direction_adapter = required_atoms, direction_adapter
        self.frames, self.sizes, self.sensor_timeout_s = frames, sizes, sensor_timeout_s
        self.encoder_factory, self.writer_factory = encoder_factory, writer_factory
        self.capture_factory = capture_factory
        self.sensors, self.queues = {}, {}
        self.encoder = self.writer = self.pipeline_capture = None
        self.count = 0

    def __enter__(self):
        try:
            for name in CAMERAS:
                mount = self.camera_mounts[name]
                if set(mount) != {"transform", "attach_to"} or mount["attach_to"] not in (None, "ego", "through", "officer"):
                    raise ValueError("Invalid original officer camera mount: " + name)
                parent = self.actors.get(mount["attach_to"])
                if mount["attach_to"] is not None and parent is None:
                    raise ValueError("Camera attachment actor missing: " + name)
                options = {} if parent is None else {"attach_to": parent}
                sensor = self.world.spawn_actor(self.camera_blueprints[name], mount["transform"], **options)
                if sensor is None:
                    raise ValueError("Original officer camera spawn failed: " + name)
                self.sensors[name] = sensor
                self.queues[name] = Queue()
                sensor.listen(self.queues[name].put)
            self.encoder = self.encoder_factory(self.root, sizes=self.sizes)
            self.encoder.__enter__()
            self.writer = self.writer_factory(self.root, self.context)
            self.writer.__enter__()
            if self.capture_factory is None:
                from pipeline_capture import PipelineCapture
                self.capture_factory = PipelineCapture
            self.pipeline_capture = self.capture_factory(
                self.client, self.actors["ego"], self.root, self.case_id,
                required_observations=self.required_atoms)
            return self
        except BaseException:
            self._close(abort=True)
            raise

    def capture_tick(self):
        if self.count >= self.frames:
            raise ValueError("Officer capture exceeds selected frame plan")
        pose = apply_direction(self.actors.get("officer"), self.direction_adapter,
                               self.case_id, self.count, self.frames)
        frame = self.world.tick()
        if type(frame) is not int:
            raise ValueError("Native tick has no integer frame identity")
        packets = {}
        for name in CAMERAS:
            try:
                packet = self.queues[name].get(timeout=self.sensor_timeout_s)
            except Empty as exc:
                raise ValueError("Original officer camera frame missing: " + name) from exc
            if packet.frame != frame:
                raise ValueError("Original officer camera frame differs: " + name)
            packets[name] = packet
        self.encoder.validate_packets(packets)
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Native snapshot differs from camera frame")
        row = self.writer.add_tick(snapshot, packets, self.actors["ego"],
                                   self.actors.get("officer"), pose)
        self.encoder.add_packets(packets)
        self.pipeline_capture.capture(frame, row["time_s"])
        self.count += 1
        return row

    def _close(self, abort):
        failure = None
        if self.pipeline_capture is not None:
            try:
                self.pipeline_capture.close(confirmed=not abort)
            except BaseException as exc:
                failure = exc
        if self.writer is not None:
            try:
                self.writer.__exit__(None, None, None)
            except BaseException as exc:
                failure = failure or exc
        for sensor in reversed(list(self.sensors.values())):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as exc:
                failure = failure or exc
        if self.encoder is not None and self.encoder.processes:
            try:
                self.encoder._finish(abort=abort or failure is not None)
            except BaseException as exc:
                failure = failure or exc
        if failure is not None:
            raise failure

    def __exit__(self, kind, value, trace):
        self._close(abort=kind is not None or self.count != self.frames)
        if kind is None and self.count != self.frames:
            raise ValueError("Officer capture ended before selected frame plan")
        return False
