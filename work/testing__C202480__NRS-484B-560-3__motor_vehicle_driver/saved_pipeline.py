"""Run postcapture media and saved analysis after the Native owner exits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_media import finalize as finalize_media
from saved_measurement import finalize_attempt


def process(attempt: Path, *, media_finalizer=finalize_media,
            measurement_finalizer=finalize_attempt) -> dict:
    attempt = Path(attempt).resolve()
    root = Path(__file__).resolve().parents[2] / ".runtime-work"
    if root not in attempt.parents:
        raise ValueError("saved processing must stay under .runtime-work")
    status_path = attempt / "native-run-status.json"
    if not status_path.is_file():
        raise ValueError("closed Native status missing")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if (status.get("errors") != [] or
            not isinstance(status.get("capture"), dict) or
            status["capture"].get("frames") != 900 or
            not isinstance(status.get("restoration"), dict) or
            status["restoration"].get("restored") is not True or
            status.get("retained_site_packet") != "site/packet.json"):
        raise ValueError("closed original Native capture and restoration required")
    media = media_finalizer(attempt)
    report = measurement_finalizer(attempt, attempt / "analysis-report.json")
    return {"media_receipt": media, "saved_report": report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(process(args.attempt), indent=2))
