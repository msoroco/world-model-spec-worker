"""Source-bound saved measurement adapter for the parking-law witness."""
import hashlib
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent.parent
_spec=importlib.util.spec_from_file_location("measure_park",HERE/"native/measure_park.py")
_module=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
measure=_module.measure


def measure_case_sources(folder: Path) -> dict:
    source=folder/"native_parking_history.json"
    if not source.is_file():
        raise ValueError("Missing required source: native_parking_history.json")
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    result=measure(source,digest)
    return {"method":"measure_case_sources","value":result,
            "sources":{"native_parking_history.json":digest}}
