"""Four synchronized original Native sensor streams for subsection 2 capture."""

from queue import Empty, Queue

from officer_camera import CAMERAS, FourCameraEncoder


class CameraMedia:
    def __init__(self, world, root, blueprints, mounts, actors, *, sizes=None,
                 timeout_s=10, encoder_factory=FourCameraEncoder):
        if set(blueprints) != set(CAMERAS) or set(mounts) != set(CAMERAS):
            raise ValueError("Four camera blueprints and mounts required")
        if not isinstance(actors, dict) or "ego" not in actors:
            raise ValueError("Native camera actor map required")
        if type(timeout_s) not in (int, float) or timeout_s <= 0:
            raise ValueError("Positive camera wait timeout required")
        self.world, self.root, self.blueprints = world, root, blueprints
        self.mounts, self.actors = mounts, actors
        self.sizes, self.timeout_s = sizes, timeout_s
        self.encoder_factory = encoder_factory
        self.encoder = None
        self.sensors = {}
        self.queues = {}

    def __enter__(self):
        try:
            for name in CAMERAS:
                mount = self.mounts[name]
                if (not isinstance(mount, dict) or set(mount) != {"transform", "attach_to"} or
                        mount["attach_to"] not in (None, "ego", "other", "officer")):
                    raise ValueError("Invalid original camera mount: " + name)
                parent = self.actors.get(mount["attach_to"])
                if mount["attach_to"] is not None and parent is None:
                    raise ValueError("Camera attachment actor missing: " + name)
                kwargs = {} if parent is None else {"attach_to": parent}
                sensor = self.world.spawn_actor(self.blueprints[name], mount["transform"], **kwargs)
                if sensor is None:
                    raise ValueError("Native camera spawn failed: " + name)
                self.sensors[name] = sensor
                self.queues[name] = Queue()
                sensor.listen(self.queues[name].put)
            self.encoder = self.encoder_factory(self.root, sizes=self.sizes)
            self.encoder.__enter__()
            return self
        except BaseException:
            self._close(abort=True)
            raise

    def readback(self, native_frame):
        if type(native_frame) is not int or self.encoder is None:
            raise ValueError("Native camera frame or media writer missing")
        packets = {}
        for name in CAMERAS:
            try:
                packet = self.queues[name].get(timeout=self.timeout_s)
            except Empty as exc:
                raise ValueError("Original camera packet missing: " + name) from exc
            if getattr(packet, "frame", None) != native_frame:
                raise ValueError("Original camera packet frame mismatch: " + name)
            packets[name] = packet
        self.encoder.validate_packets(packets)
        video_index = self.encoder.count
        self.encoder.add_packets(packets)
        return {name: {"carla_frame": native_frame,
                       "raw_source": str(self.encoder.root / (name + ".mkv")) +
                       "#frame-" + str(video_index),
                       "video_frame": video_index,
                       "width": packets[name].width, "height": packets[name].height}
                for name in CAMERAS}

    def _close(self, abort):
        failure = None
        for sensor in reversed(list(self.sensors.values())):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as exc:
                failure = failure or exc
        self.sensors = {}
        if self.encoder is not None and self.encoder.processes:
            try:
                self.encoder._finish(abort=abort or failure is not None)
            except BaseException as exc:
                failure = failure or exc
        if failure is not None:
            raise failure

    def __exit__(self, kind, value, trace):
        self._close(abort=kind is not None)
        return False
