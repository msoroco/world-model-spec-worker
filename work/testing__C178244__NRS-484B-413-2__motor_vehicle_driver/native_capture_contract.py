"""Fixed four-view and 20 Hz original acquisition contract."""

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAMES = 900
STEP_S = 0.05
