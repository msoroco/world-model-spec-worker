"""Independently recompute six synthetic clear/rain weather-control pairs."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from saved_measure import process


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    receipt = json.loads((HERE / "synthetic-weather-control.json").read_text())
    assert receipt["passed"] is True and receipt["cases"] == 6
    assert receipt["native_executed"] is False
    assert [item["feet"] for item in receipt["records"]] == [90, 100, 110, 290, 300, 310]
    for item in receipt["records"]:
        clear = HERE / item["clear_source"]
        rain = HERE / item["rain_source"]
        assert sha(clear) == item["clear_sha256"] and sha(rain) == item["rain_sha256"]
        assert sha(rain.parent / "config.json") == item["rain_config_sha256"]
        dry_rows = rows(clear)
        wet_rows = rows(rain)
        assert len(dry_rows) == len(wet_rows) == 840
        for dry, wet in zip(dry_rows, wet_rows):
            assert dry.pop("weather") == "clear_noon"
            assert wet.pop("weather") == "heavy_rain_noon"
            assert dry == wet
        dry = process(clear.parent, clear.parent / "config.json")
        wet = process(rain.parent, rain.parent / "config.json")
        assert dry["continuous_signal_distance_ft"] == wet["continuous_signal_distance_ft"]
        assert abs(wet["continuous_signal_distance_ft"] - item["measured_ft"]) < 1e-9
        assert abs(wet["continuous_signal_distance_ft"] - item["feet"]) < .5
        try:
            process(rain.parent, clear.parent / "config.json")
        except ValueError as error:
            assert "saved area/weather context differs" in str(error)
        else:
            raise AssertionError("Mismatched source weather passed")
    result = {"format": "c104393-independent-weather-audit-v1", "passed": True,
              "controlled_pairs": 6, "mismatch_negatives": 6,
              "synthetic": True, "native_executed": False,
              "receipt_sha256": sha(HERE / "synthetic-weather-control.json")}
    (HERE / "independent-weather-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
