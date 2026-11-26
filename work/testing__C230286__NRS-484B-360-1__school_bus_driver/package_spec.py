"""Exact NRS 484B.360(1) source and recording contract."""

AID = "testing__C230286__NRS-484B-360-1__school_bus_driver"
LAW = "NRS-484B-360-1"
CELL = "C230286"
ACTOR = "school_bus_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if i == 0 else 1280,
            "height": 1080 if i == 0 else 720, "fov_deg": 75,
            "pose_strategy": "source-surveyed bus route, sidewalk and pupil boarding context"}
           for i, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ("school_bus_classification", "source record", "source-sealed definition branch and exclusions"),
    ("driver_and_bus_identity", "source record", "source-sealed driver and Native bus identity"),
    ("pupil_transport_phase", "boolean/frame", "source-sealed trip interval joined to Native frame time"),
    ("pupil_presence_count", "persons", "independent source-sealed pupil count and presence"),
    ("bus_speed", "miles/hour/frame", "Native bus velocity norm at 20 Hz"),
    ("bus_route_position", "world meters/frame", "Native bus pose along surveyed route"),
    ("sidewalk_relation", "source record", "surveyed sidewalk and access relation"),
)
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second school-bus speed interval",
                  "reference_frame": "reviewed Native route and bus frame",
                  "uncertainty": "Original measurements do not prove pupil-trip legal status"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [{"name": "reviewed_school_bus_trip", "unit": "source record",
                        "method": "sealed definition, exclusions, trip purpose, pupils and sidewalk survey"}],
    "limitations": ["Commanded 54, 55 or 56 mph does not establish realized speed.",
                    "School-bus status and pupil trip require independent source review.",
                    "Synthetic diagnostics are software proofs only."]}
