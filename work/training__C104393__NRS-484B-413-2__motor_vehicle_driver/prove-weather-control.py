"""Retain six source-hashed clear/rain controlled saved-measurement pairs."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from saved_measure import process
from engineering import parameters


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    records = []
    for feet in (90, 100, 110, 290, 300, 310):
        clear = HERE / "synthetic-saved-fixtures" / str(feet)
        rain = HERE / "synthetic-weather-fixtures" / str(feet)
        rain.mkdir(parents=True, exist_ok=True)
        config = json.loads((clear / "config.json").read_text())
        config["native_request"]["weather"] = "heavy_rain_noon"
        assert parameters(config)["weather"] == "heavy_rain_noon"
        (rain / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        shutil.copyfile(clear / "road_geometry.json", rain / "road_geometry.json")
        clear_rows = read_rows(clear / "native_samples.jsonl")
        rain_rows = [{**row, "weather": "heavy_rain_noon"} for row in clear_rows]
        assert len(rain_rows) == 840
        assert all({k: v for k, v in a.items() if k != "weather"} ==
                   {k: v for k, v in b.items() if k != "weather"}
                   for a, b in zip(clear_rows, rain_rows))
        source = rain / "native_samples.jsonl"
        source.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n"
                                  for row in rain_rows))
        dry = process(clear, clear / "config.json")
        wet = process(rain, rain / "config.json")
        assert dry["weather"] == "clear_noon" and wet["weather"] == "heavy_rain_noon"
        assert dry["continuous_signal_distance_ft"] == wet["continuous_signal_distance_ft"]
        try:
            process(rain, clear / "config.json")
        except ValueError as error:
            assert "saved area/weather context differs" in str(error)
        else:
            raise AssertionError("Mismatched weather request accepted")
        records.append({"feet": feet, "clear_source": str((clear / "native_samples.jsonl").relative_to(HERE)),
                        "clear_sha256": sha(clear / "native_samples.jsonl"),
                        "rain_source": str(source.relative_to(HERE)),
                        "rain_sha256": sha(source),
                        "rain_config_sha256": sha(rain / "config.json"),
                        "measured_ft": wet["continuous_signal_distance_ft"],
                        "nonweather_fields_equal": True,
                        "mismatch_negative_rejected": True})
    receipt = {"format": "c104393-synthetic-weather-control-v1", "passed": True,
               "cases": len(records), "native_executed": False,
               "physical_weather_claimed": False, "records": records}
    (HERE / "synthetic-weather-control.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(records)}))


if __name__ == "__main__":
    main()
