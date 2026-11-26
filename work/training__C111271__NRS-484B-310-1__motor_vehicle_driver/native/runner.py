"""Check the authored 30-second flashing-red approach contract offline."""
import argparse
import json
from pathlib import Path

from controller import State, command

HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / "config.json").read_text())
    if config["frames"] != 600 or config["rate_hz"] != 20:
        raise ValueError("Exact 30-second source contract differs")
    if config["cell_id"] != "C111271" or config["law_id"] != "NRS-484B-310-1" or \
            config["actor"] != "motor_vehicle_driver":
        raise ValueError("Frozen assignment identity differs")
    if set(config["camera_sources"]) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("Four source cameras required")
    if len(config.get("supported_case_ids", [])) != 6:
        raise ValueError("Six exact reference/stop cases required")
    selected = config.get('selected_case_id')
    if selected not in config['supported_case_ids'] or config.get('case_id') != selected:
        raise ValueError('Exact selected case identity differs')
    suffix = selected.rsplit('__', 1)[-1]
    reference = ('limit_line' if suffix in ('probe_a', 'probe_b') else
                 'crosswalk' if suffix.startswith('crosswalk_') else 'intersection')
    if config.get('reference_kind') != reference or \
            config.get('requested_halt') != (suffix in ('probe_a', 'crosswalk_stop', 'intersection_stop')):
        raise ValueError('Exact stopping-reference branch or controlled halt differs')
    line, walk, edge = (config[key] for key in
                        ('limit_line_x_m', 'crosswalk_near_x_m', 'intersection_near_x_m'))
    geometry_ok = (0 < line < walk < edge < 100 if reference == 'limit_line' else
                   line is None and 0 < walk < edge < 100 if reference == 'crosswalk' else
                   line is None and walk is None and 0 < edge < 100)
    if not geometry_ok:
        raise ValueError("Authored stopping-reference geometry differs")
    for stopping, nonstop_case, reference in (("probe_a", "probe_b", 48.0),
                                              ("crosswalk_stop", "crosswalk_no_stop", 50.0),
                                              ("intersection_stop", "intersection_no_stop", 52.0)):
        stopped = State()
        first = command(stopping, reference - 2, 5.0, reference, False, stopped)
        if first["engineering_phase"] != "pre_reference_stop":
            raise ValueError("Stop controller did not brake before reference")
        for _ in range(30):
            after = command(stopping, reference - 2, 0.0, reference, False, stopped)
        if after["engineering_phase"] != "proceed":
            raise ValueError("Stop controller did not release after hold")
        nonstop = command(nonstop_case, reference - 2, 5.0, reference, False, State())
        if nonstop["engineering_phase"] != "proceed":
            raise ValueError("Nonstop comparison controller differs")
    return {"case_id": config["case_id"], "frames": 600, "rate_hz": 20,
            "source_cameras_planned": 4, "exact_cases_checked": 6,
            "controller_hold_frames_tested": 30,
            "native_executed": False,
            "physical_signal_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--context-survey", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    checked = check()
    if args.check:
        print(json.dumps(checked, sort_keys=True))
        return
    if args.output_dir is None:
        raise ValueError("Fresh materialized Native output directory required")
    from capture import execute
    config = json.loads((HERE / "config.json").read_text())
    execute(config, args.output_dir, args.host, args.port, args.context_survey)


if __name__ == "__main__":
    main()
