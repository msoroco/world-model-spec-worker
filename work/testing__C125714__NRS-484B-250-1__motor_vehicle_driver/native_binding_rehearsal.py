"""CPU rehearsal of the Native spawn gate against all diagnostic route anchors.

The waypoint graph is a stand-in assembled from the separately screened
OpenDRIVE route sequences. It tests the binding and pre-spawn rejection code;
it does not claim CARLA loaded the candidate map.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_driver import spawn_vehicles
from opendrive_route_preflight import preflight


class Waypoint:
    def __init__(self, road, junction, x, y):
        self.road_id = int(road)
        self.lane_id = -1
        self.is_junction = junction
        self.transform = type("Pose", (), {"location": type("Point", (), {"x": x, "y": y})()})()
        self.successors = []

    def next(self, distance):
        return self.successors


class RehearsalMap:
    def __init__(self, source, scene, routes, disconnect=None):
        self.source = source
        self.nodes = {}
        for party in ("ego", "other"):
            anchors = scene[f"{party}_route_xy_m"]
            roads = routes[party]["road_sequence"]
            if len(anchors) != len(roads):
                raise ValueError("screened road sequence does not match route anchors")
            nodes = []
            for (x, y), road in zip(anchors, roads):
                key = (x, y)
                node = Waypoint(road, 100 <= int(road) < 200, x, y)
                if key in self.nodes:
                    prior = self.nodes[key]
                    if prior.road_id != node.road_id:
                        raise ValueError("ambiguous route anchor road identity")
                    node = prior
                self.nodes[key] = node
                nodes.append(node)
            for index, (first, second) in enumerate(zip(nodes, nodes[1:])):
                if disconnect == (party, index):
                    continue
                if second not in first.successors:
                    first.successors.append(second)

    def to_opendrive(self):
        return self.source

    def get_waypoint(self, point, project_to_road=False):
        if project_to_road:
            raise ValueError("rehearsal must not project off-road points")
        return self.nodes.get(point)


class RehearsalWorld:
    def __init__(self, mapping):
        self.mapping = mapping
        self.spawned = []

    def get_map(self):
        return self.mapping

    def get_blueprint_library(self):
        class Blueprint:
            def set_attribute(self, key, value):
                pass

        class Library:
            def filter(self, pattern):
                return [Blueprint()]

        return Library()

    def spawn_actor(self, blueprint, pose):
        class Actor:
            def __init__(self, ident):
                self.id = ident
                self.destroyed = False

            def destroy(self):
                self.destroyed = True

        actor = Actor(len(self.spawned) + 1)
        self.spawned.append(actor)
        return actor


class CarlaStandIn:
    @staticmethod
    def Location(x, y, z):
        return x, y


def rehearse(root):
    root = Path(root)
    source = (root / "connected-median-candidate.xodr").read_text()
    from connected_map_candidate import inspect
    geometry = inspect(root / "connected-median-candidate.xodr")
    scenes = [root / "scene.json", *sorted((root / "cases").glob("*/scene.json"))]
    screened = preflight(root / "connected-median-candidate.xodr", scenes)
    if (hashlib.sha256(source.encode()).hexdigest() != screened["map_sha256"] or
            geometry["map_sha256"] != screened["map_sha256"]):
        raise ValueError("screened source bytes changed")
    outcomes = {}
    for path in scenes:
        scene = json.loads(path.read_text())
        routes = screened["cases"][scene["case_id"]]
        world = RehearsalWorld(RehearsalMap(source, scene, routes))
        actors = spawn_vehicles(world, scene, CarlaStandIn)
        if set(actors) != {"ego", "other"} or len(world.spawned) != 2:
            raise ValueError("two distinct actors were not spawned")
        broken = RehearsalWorld(RehearsalMap(source, scene, routes, ("ego", 0)))
        try:
            spawn_vehicles(broken, scene, CarlaStandIn)
        except ValueError as error:
            if "forward Native waypoint connectivity" not in str(error):
                raise
        else:
            raise ValueError("disconnected route was accepted")
        if broken.spawned:
            raise ValueError("spawn occurred before route rejection")
        outcomes[scene["case_id"]] = {
            "bound_parties": sorted(actors), "spawned_count": len(world.spawned),
            "disconnected_pre_spawn_rejected": True,
            "road_sequences": {party: routes[party]["road_sequence"] for party in ("ego", "other")},
        }
    return {"format": "c125714-diagnostic-native-binding-rehearsal-v1",
            "map_sha256": screened["map_sha256"], "cases": outcomes,
            "limitations": "CPU waypoint stand-in only; live CARLA load, motion and legal context unverified."}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    Path(args.output).write_text(json.dumps(rehearse(base), indent=2) + "\n")
