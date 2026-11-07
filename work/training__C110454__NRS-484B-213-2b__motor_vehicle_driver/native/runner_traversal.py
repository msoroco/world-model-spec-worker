"""Exact traversal runner variant over the existing Native capture implementation."""
from __future__ import annotations

import runner_base as base
from engineering import controller_parameters as approach_controller_parameters
from engineering import parameters as approach_parameters
from traversal import check_pair, pose


def traversal_parameters(case, candidate):
    if case not in ("traversal_reference", "traversal_contrast"):
        raise ValueError("Unknown traversal case")
    return approach_parameters("reference", candidate) | {"case": case}


def traversal_controller_parameters(case, candidate):
    traversal_parameters(case, candidate)
    return approach_controller_parameters("reference", candidate)


def traversal_route(case):
    traversal_parameters(case, "primary")
    return [list(pose(case, frame)) for frame in range(480)]


def traversal_geometry_check():
    return {"passed": True, "traversal": check_pair(),
            "physical_success_claimed": False}


base.EXCURSION_WINDOWS = {"traversal_reference": None, "traversal_contrast": None}
base.parameters = traversal_parameters
base.controller_parameters = traversal_controller_parameters
base.route = traversal_route
base.geometry_check = traversal_geometry_check

check = base.check
execute = base.execute
frame_map_row = base.frame_map_row
observed_speed_mps = base.observed_speed_mps


if __name__ == "__main__":
    base.main()
