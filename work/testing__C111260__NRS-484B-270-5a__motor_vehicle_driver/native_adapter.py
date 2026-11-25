"""Owned Native actor setup for the sealed C111260 rider encounter.

This module deliberately leaves camera acquisition and physical completion to
the live runner. It rejects an unreviewed site before changing the world.
"""

from __future__ import annotations

from copy import copy
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent


def _module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENCOUNTER = _module("cyclist_encounter")
NATIVE_SITE = _module("native_site")


def _transform(carla, waypoint):
    return carla.Transform(
        carla.Location(x=waypoint["x_m"], y=waypoint["y_m"], z=waypoint["z_m"]),
        carla.Rotation(yaw=waypoint["yaw_deg"]))


class OwnedEncounter:
    def __init__(self, world, carla, survey_root, site_ref, rider_kind):
        self.world = world
        self.carla = carla
        self.survey_root = survey_root
        self.site_ref = site_ref
        self.rider_kind = rider_kind
        self.original_settings = None
        self.actors = None
        self.site = None
        self.closed = False

    def open(self):
        if self.original_settings is not None:
            raise ValueError("Native encounter already opened")
        self.site = NATIVE_SITE.verify_live(
            self.world, self.carla, self.survey_root, self.site_ref,
            expected_kind=self.rider_kind)
        self.original_settings = copy(self.world.get_settings())
        try:
            settings = copy(self.original_settings)
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = 0.05
            self.world.apply_settings(settings)
            self.actors = ENCOUNTER.spawn_encounter(
                self.world, self.site, self.rider_kind,
                lambda position: _transform(self.carla, position))
            person_id = int(self.site["rider"]["person_actor_id"])
            person = self.world.get_actor(person_id)
            if (person is None or getattr(person, "id", None) != person_id
                    or person_id == self.actors["ego"].id):
                raise ValueError("original rider person actor unavailable")
            self.actors["person"] = person
            return self
        except Exception:
            self.close()
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        if self.actors is not None:
            for actor in (self.actors["rider"], self.actors["ego"]):
                try:
                    actor.destroy()
                except Exception as error:
                    errors.append(error)
        if self.original_settings is not None:
            try:
                self.world.apply_settings(self.original_settings)
                restored = self.world.get_settings()
                if (restored.synchronous_mode != self.original_settings.synchronous_mode
                        or restored.fixed_delta_seconds != self.original_settings.fixed_delta_seconds):
                    raise ValueError("Native world restoration readback differs")
            except Exception as error:
                errors.append(error)
        if errors and sys.exc_info()[0] is None:
            raise RuntimeError("Native encounter cleanup failed") from errors[0]

    def __enter__(self):
        return self.open()

    def __exit__(self, *_):
        self.close()
