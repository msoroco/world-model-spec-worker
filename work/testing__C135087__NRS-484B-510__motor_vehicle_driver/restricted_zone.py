"""Lazy Native construction for the C135087 restricted-zone comparisons.

This module makes the physical cause inspectable and records intended setup. It
does not classify a stop as lawful or prove that a sign is authoritative.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ZonePlan:
    case_id: str
    map_id: str
    zone_start_m: float
    zone_end_m: float
    subject_stop_m: float
    entrant_start_m: float
    entrant_destination_m: float
    entrant_departure_s: float
    subject_departure_s: float
    passenger_exchange_start_s: float
    passenger_exchange_end_s: float
    restricted_purpose: str = "reserved vehicle parking"
    restricted_source: str = "authored zone context pending independent authority review"

    def validate(self) -> None:
        if not self.case_id or not self.map_id:
            raise ValueError("case and map identities required")
        if not self.zone_start_m < self.subject_stop_m < self.zone_end_m:
            raise ValueError("subject stop must lie inside restricted zone")
        if not self.entrant_start_m < self.zone_start_m:
            raise ValueError("entrant approach must begin before zone")
        if not self.zone_start_m < self.entrant_destination_m < self.zone_end_m:
            raise ValueError("entrant parking destination must lie in zone")
        if not 0 <= self.passenger_exchange_start_s < self.passenger_exchange_end_s:
            raise ValueError("actual passenger exchange interval required")
        if self.subject_departure_s < self.passenger_exchange_end_s:
            raise ValueError("subject must remain through passenger exchange")
        if self.entrant_departure_s < 0:
            raise ValueError("entrant departure cannot precede capture")


class NativeWorld(Protocol):
    def load_map(self, map_id: str): ...
    def mark_zone(self, start_m: float, end_m: float, purpose: str, source: str): ...
    def spawn_vehicle(self, role: str, station_m: float, vehicle_class: str): ...
    def spawn_pedestrian(self, role: str, station_m: float): ...
    def set_route(self, actor, destination_m: float): ...
    def schedule(self, actor, action: str, at_s: float): ...


def construct(plan: ZonePlan, world: NativeWorld) -> dict:
    """Build both vehicles, their routes, zone and observable exchange schedule."""
    plan.validate()
    world.load_map(plan.map_id)
    world.mark_zone(plan.zone_start_m, plan.zone_end_m,
                    plan.restricted_purpose, plan.restricted_source)
    subject = world.spawn_vehicle("subject", plan.subject_stop_m, "passenger-vehicle-candidate")
    entrant = world.spawn_vehicle("restricted-purpose-entrant", plan.entrant_start_m,
                                  "reserved-purpose-vehicle-candidate")
    passenger = world.spawn_pedestrian("passenger", plan.subject_stop_m)
    world.set_route(entrant, plan.entrant_destination_m)
    world.set_route(passenger, plan.subject_stop_m)
    world.schedule(passenger, "approach_subject_door", plan.passenger_exchange_start_s)
    world.schedule(passenger, "complete_boarding_or_alighting", plan.passenger_exchange_end_s)
    world.schedule(subject, "passenger_exchange_start", plan.passenger_exchange_start_s)
    world.schedule(subject, "passenger_exchange_end", plan.passenger_exchange_end_s)
    world.schedule(subject, "depart_zone", plan.subject_departure_s)
    world.schedule(entrant, "start_approach", plan.entrant_departure_s)
    world.schedule(entrant, "request_reserved_parking", plan.entrant_departure_s)
    return {"subject": subject, "entrant": entrant, "passenger": passenger,
            "case_id": plan.case_id}
