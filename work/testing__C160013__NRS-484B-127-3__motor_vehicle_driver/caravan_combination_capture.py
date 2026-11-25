"""Add original drawn-unit state to each Native caravan history row."""
import json

from caravan_capture import state


class CombinationHistory:
    def __init__(self, destination, drawing_actor, drawn_actor):
        if drawing_actor.id == drawn_actor.id:
            raise ValueError("Distinct original towing actors required")
        self.destination = destination
        self.drawing_actor = drawing_actor
        self.drawn_actor = drawn_actor

    def write(self, line):
        row = json.loads(line)
        members = row.get("caravan_members")
        if not isinstance(members, list) or self.drawing_actor.id not in {m.get("actor_id") for m in members}:
            raise ValueError("Original drawing actor missing from caravan frame")
        if row.get("entering_vehicle", {}).get("actor_id") == self.drawn_actor.id or any(
                m.get("actor_id") == self.drawn_actor.id for m in members):
            raise ValueError("Drawn unit duplicates a powered participant")
        unit = state(self.drawn_actor)
        if unit["actor_id"] != self.drawn_actor.id:
            raise ValueError("Original drawn-unit actor identity changed")
        row["drawn_units"] = [{key: unit[key] for key in
                              ("actor_id", "blueprint_id", "body_vertices_xy_m")}]
        row["towing_relationship"] = {"drawing_actor_id": self.drawing_actor.id,
                                      "drawn_actor_id": self.drawn_actor.id}
        return self.destination.write(json.dumps(row, separators=(",", ":")) + "\n")
