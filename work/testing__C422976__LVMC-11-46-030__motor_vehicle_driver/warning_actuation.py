"""Source-gated physical warning, release and child motion requests.

Raw Native readback is retained. A command or readback never assigns the legal
meaning of a human warning, go signal or departure from the locality.
"""


def require_sources(schedule, human, device, child):
    kind = schedule["requested_warning_actor"]
    release = schedule["requested_release"]
    if kind in ("human", "human_present"):
        for name in ("flag_blueprint_id", "flag_parked_pose", "flag_warning_pose",
                     "flag_go_pose", "departure_velocity_xy_mps"):
            if not human.get(name):
                raise ValueError("reviewed human flag source missing: " + name)
        if not human["flag_blueprint_id"].startswith("static.prop."):
            raise ValueError("reviewed Native flag blueprint required")
    if kind == "device":
        for name in ("warning_state", "released_state"):
            if not device.get(name):
                raise ValueError("reviewed device state source missing: " + name)
    if kind in ("human", "device"):
        if not child.get("child_classification_source"):
            raise ValueError("reviewed child classification source required")
        if not child.get("crossing_velocity_xy_mps"):
            raise ValueError("reviewed child crossing motion source required")
    if release == "go" and kind != "human":
        raise ValueError("human go request needs human warning actor")
    if release == "depart" and kind != "human":
        raise ValueError("human departure request needs human warning actor")
    if release == "raised" and kind != "device":
        raise ValueError("device release request needs warning device")


class WarningActuator:
    def __init__(self, schedule, human, device, child, adapter):
        require_sources(schedule, human, device, child)
        self.schedule = schedule
        self.human = human
        self.device = device
        self.child = child
        self.adapter = adapter

    def request(self, frame):
        kind = self.schedule["requested_warning_actor"]
        onset = self.schedule["warning_on_from_frame"]
        release = self.schedule["release_frame"]
        if kind in ("human", "human_present"):
            pose = self.human["flag_parked_pose"]
            if kind == "human" and onset is not None and frame >= onset:
                pose = self.human["flag_warning_pose"]
            if self.schedule["requested_release"] == "go" and release is not None and frame >= release:
                pose = self.human["flag_go_pose"]
            self.adapter.set_flag_pose(pose)
        if kind == "device":
            state = self.device["warning_state"]
            if release is not None and frame >= release:
                state = self.device["released_state"]
            self.adapter.set_device_state(state)
        if kind == "human" and self.schedule["requested_release"] == "depart":
            if release is not None and frame >= release:
                self.adapter.move_human(self.human["departure_velocity_xy_mps"])
        if kind in ("human", "device"):
            children_on = self.schedule["children_crossing_from_frame"]
            if children_on is not None and frame >= children_on:
                self.adapter.move_child(self.child["crossing_velocity_xy_mps"])

    def readback(self):
        return {"flag_pose": self.adapter.read_flag_pose(),
                "device_state": self.adapter.read_device_state(),
                "human_location_xyz": self.adapter.read_human_location(),
                "child_location_xyz": self.adapter.read_child_location(),
                "legal_warning_or_release_judgment": "unresolved"}
