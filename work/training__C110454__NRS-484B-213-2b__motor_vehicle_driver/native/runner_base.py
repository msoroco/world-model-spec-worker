"""Hookable retained Native runner used by the traversal draft variant."""

import runner as _runner

EXCURSION_WINDOWS = _runner.EXCURSION_WINDOWS
parameters = _runner.parameters
controller_parameters = _runner.controller_parameters
route = _runner.route
geometry_check = _runner.geometry_check
frame_map_row = _runner.frame_map_row
observed_speed_mps = _runner.observed_speed_mps


def _bind() -> None:
    _runner.EXCURSION_WINDOWS = EXCURSION_WINDOWS
    _runner.parameters = parameters
    _runner.controller_parameters = controller_parameters
    _runner.route = route
    _runner.geometry_check = geometry_check


def check(config):
    _bind()
    return _runner.check(config)


def execute(config, output, host, port):
    _bind()
    return _runner.execute(config, output, host, port)


def main():
    _bind()
    return _runner.main()
