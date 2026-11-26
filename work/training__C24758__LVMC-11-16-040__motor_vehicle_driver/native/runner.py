"""C24758 exact reference primary offline and saved-source entrypoint."""
import argparse
import json
from pathlib import Path

from saved_source import CAMERAS, check_saved
from sight_speed_measure import EXPECTED_ID, require


def check():
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    require(config.get("case_id") in (EXPECTED_ID + "__reference", EXPECTED_ID + "__at_15",
                                      EXPECTED_ID + "__contrast"), "case mismatch")
    require((config.get("law_id"), config.get("cell_id"), config.get("actor")) ==
            ("LVMC-11-16-040", "C24758", "motor_vehicle_driver"),
            "law/cell/actor mismatch")
    require(config.get("duration_s") == 30 and config.get("rate_hz") == 20,
            "capture timing mismatch")
    require(config.get("target_speed_mps") == {
                "reference": 6.2, "at_15": 6.7056, "contrast": 7.2
            }[config["case_id"].rsplit("__", 1)[-1]], "case speed mismatch")
    require((config.get("throttle_gain"), config.get("brake_gain"))
            in ((0.12, 0.18), (0.16, 0.22)), "unreviewed controller tuning")
    require([c.get("name") for c in config.get("cameras", [])] == list(CAMERAS),
            "camera plan mismatch")
    require(all(c.get("width", 0) >= 64 and c.get("height", 0) >= 64
                for c in config["cameras"]), "camera dimensions missing")
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--output")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--junction-id", type=int)
    args = parser.parse_args()
    config = check()
    if args.check:
        print("PASS exact primary case, 30 seconds, 20 Hz, four camera plan")
        return
    if args.attempt and args.output:
        check_saved(args.attempt, args.output, config["case_id"])
        print("PASS saved-source join; physical acceptance unconfirmed")
        return
    if args.output_dir:
        from native_capture import capture
        print(json.dumps(capture(config, args.output_dir, args.host, args.port,
                                 args.junction_id)))
        return
    parser.error("Provide --check, --attempt and --output, or --output-dir")


if __name__ == "__main__":
    main()
