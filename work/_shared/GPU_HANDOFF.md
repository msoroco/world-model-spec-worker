# First GPU capability commands

CPU preparation only. Set CARLA_PYTHON, CARLA_HOST, and CARLA_PORT on the local Native host. These commands check Native imports before creating a new attempt. No CARLA run or physical/legal acceptance is claimed.

## demo-test-01

### testing__C109705__NRS-484B-400-2a__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/execution-manifest.json --case testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__selected_left_turn --output .runtime-work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native left-turn connection and actual route progression
- Original full-body centerline position and complete 45s duration
- Four original camera pixels, frame sync and composition
- Public highway status and legal interpretation

### testing__C109705__NRS-484B-400-2b__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/execution-manifest.json --case testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__selected_left_turn --output .runtime-work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native left-turn connection and actual route progression
- Original full-body centerline position and complete 45s duration
- Four original camera pixels, frame sync and composition
- Public highway status and legal interpretation

### testing__C109749__NRS-484B-253__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C109749__NRS-484B-253__motor_vehicle_driver/execution-manifest.json --case testing__C109749__NRS-484B-253__motor_vehicle_driver__selected_initial_yield --output .runtime-work/testing__C109749__NRS-484B-253__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native opposing vehicle trajectory and full-body intersection occupancy
- Subject observed release only after counterpart clearance
- Original signal lamp pixels, four-view visibility and full duration
- Immediate hazard, priority and legal judgment

### testing__C144550__NRS-484B-223-1b__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C144550__NRS-484B-223-1b__motor_vehicle_driver/execution-manifest.json --case testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__selected_signaled_change --output .runtime-work/testing__C144550__NRS-484B-223-1b__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native one-way lane readback, marking pixels and full lane-change trajectory
- Actual emitted turn-indicator pixels and signal timing
- Target-lane body gap, surrounding traffic, and safety ascertainment
- Four-view pixel coverage and complete duration

### testing__C160013__NRS-484B-127-3__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__selected_caravan_entry --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native four-participant caravan and entrant motion, full body-gap duration
- Actual outsider lane entry and complete clearance
- Four-view original pixels and 45s final observation
- Public-way and outside-business-district facts and no-danger judgment

### testing__C331230__NRS-484A-450-2__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C331230__NRS-484A-450-2__motor_vehicle_driver/execution-manifest.json --case testing__C331230__NRS-484A-450-2__motor_vehicle_driver__selected_near_side_crosswalk --output .runtime-work/testing__C331230__NRS-484A-450-2__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native STOP landmark governance and near-side physical stripe placement
- Actual body-front stopping and continuous cessation before entry
- Four-view physical pixels, driver viewpoint and complete original 45s episode
- Public-way status and legal stop interpretation

## demo-test-02

### testing__C125714__NRS-484B-250-1__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-1__motor_vehicle_driver__median_opening_crossing --output .runtime-work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native connected road and barrier-object readback; opening must remain unobstructed
- Actual two-vehicle entry order/timing, clearance and full-body footprint trajectories
- Original four-view pixels and 55-second duration
- Public highway status, official device governance, right-of-way and subsection 4 legal review

### testing__C125714__NRS-484B-250-2__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__median_opening_timing --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native connected road and barrier-object readback; opening must remain unobstructed
- Actual two-vehicle entry order/timing, clearance and full-body footprint trajectories
- Original four-view pixels and 55-second duration
- Public highway status, official device governance, right-of-way and subsection 4 legal review

### testing__C126120__NRS-484B-227-1__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C126120__NRS-484B-227-1__motor_vehicle_driver/execution-manifest.json --case testing__C126120__NRS-484B-227-1__motor_vehicle_driver__median_opening_uturn --output .runtime-work/testing__C126120__NRS-484B-227-1__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native median barrier/opening and opposing roadway readback
- Complete U-turn route, full body footprint and direction reversal
- Four original views and full 60-second duration
- Public highway and public-authority establishment; no physical/legal verdict claimed

### testing__C147311__NRS-484B-220-1__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C147311__NRS-484B-220-1__motor_vehicle_driver/execution-manifest.json --case testing__C147311__NRS-484B-220-1__motor_vehicle_driver__one_way_designated_direction --output .runtime-work/testing__C147311__NRS-484B-220-1__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native 220 one-way sign landmark and actually rendered governing sign pixels
- Native two-lane road and projected ego motion
- Public highway designation and sign authority
- Four original source camera visibility and complete 45s duration

### testing__C179789__NRS-484B-600-1a__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C179789__NRS-484B-600-1a__motor_vehicle_driver/execution-manifest.json --case testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__paved_speed_conditions --output .runtime-work/testing__C179789__NRS-484B-600-1a__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native two-vehicle motion and complete 45-second route
- Same-frame weather and Native asphalt surface provenance
- RGB/instance target contrast calibration and source image hashes
- Actual road width, shoulder and curvature surveys
- Sight ray geometry, four-view pixels and legal reasonableness remain unconfirmed

### testing__C378304__NRS-484B-413-2__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C378304__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C378304__NRS-484B-413-2__motor_vehicle_driver__business_district_right_signal --output .runtime-work/testing__C378304__NRS-484B-413-2__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native right-turn connector and full 50-second path completion
- Actual last 100-foot approach bracket and right indicator API continuity
- Original emitted lamp pixels; body ROI photometry is not lamp verification
- Business-district frontage/use and freight-zone administrative designation
- Four-view camera coverage and legal standards

## demo-test-03

### testing__C158208__NRS-484B-257-1__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C158208__NRS-484B-257-1__motor_vehicle_driver/execution-manifest.json --case testing__C158208__NRS-484B-257-1__motor_vehicle_driver__yield_nearest_selected --output .runtime-work/testing__C158208__NRS-484B-257-1__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Actual Native sign/marking governance and original pixels
- Complete subject and through-vehicle physical motion
- Four original camera views and full final observation
- Statutory view, immediate-hazard and yield judgments

### testing__C158208__NRS-484B-257-2__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C158208__NRS-484B-257-2__motor_vehicle_driver/execution-manifest.json --case testing__C158208__NRS-484B-257-2__motor_vehicle_driver__stop_within_selected --output .runtime-work/testing__C158208__NRS-484B-257-2__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Actual Native sign/marking governance and original pixels
- Complete subject and through-vehicle physical motion
- Four original camera views and full final observation
- Statutory view, immediate-hazard and yield judgments

### testing__C129731__NRS-484B-407__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C129731__NRS-484B-407__motor_vehicle_driver/execution-manifest.json --case testing__C129731__NRS-484B-407__motor_vehicle_driver__mountain_curve_turn --output .runtime-work/testing__C129731__NRS-484B-407__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native curved OpenDRIVE and crest elevation readback
- Physical U-turn completion and body on roadway
- Both-direction 500ft actual driver-eye and pixel visibility
- All four original camera views and full final observation

### testing__C149237__NRS-484B-127-2__heavy_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__qualifying_following_gap --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native truck blueprint and both physical widths >=80in
- Single same-direction lane and complete truck routes
- Original 3D route body gap, overtaking opportunity and conditions permitting
- All four actual camera views and clearance/final observation

### testing__C215286__NRS-484B-113-2__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__backing_over_physical_crosswalk --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native reverse vehicle motion and physical crosswalk stripe mesh
- Full-body overlap at original ticks
- All four actual camera views and final observation
- Legal review of selected on-or-over branch

## demo-test-04

### testing__C101303__NRS-484B-127-1__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/execution-manifest.json --case testing__C101303__NRS-484B-127-1__motor_vehicle_driver__following_before_lane_change --output .runtime-work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native following interval and actual lane-change body route
- Crest, public-way and surface condition facts
- Four-view original pixels and complete duration
- Reasonable/prudent judgment unresolved

### testing__C10301__NRS-484B-600-1e__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C10301__NRS-484B-600-1e__motor_vehicle_driver/execution-manifest.json --case testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__selected_speed_observation --output .runtime-work/testing__C10301__NRS-484B-600-1e__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native route and motion
- Four-view original pixels and duration
- Public highway and legal context

### testing__C136559__NRS-484B-600-1c__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C136559__NRS-484B-600-1c__motor_vehicle_driver/execution-manifest.json --case testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__posted_narrow_road_observation --output .runtime-work/testing__C136559__NRS-484B-600-1c__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native physical sign and governed approach pixels
- Public authority authorization
- Native motion and in-zone speed
- Four-view original pixels and duration

### testing__C158196__NRS-484B-307-6a__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C158196__NRS-484B-307-6a__motor_vehicle_driver/execution-manifest.json --case testing__C158196__NRS-484B-307-6a__motor_vehicle_driver__yellow_to_red_entry_order --output .runtime-work/testing__C158196__NRS-484B-307-6a__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Native installed head and one-way/two-way topology
- Yellow/red original pixels, state timing and facing relation
- Full-body red-entry ordering and duration
- Official signal authority and pedestrian-head inventory

### testing__C24757__NRS-484B-250-4__motor_vehicle_driver

```sh
.venv-cpu/bin/python runtime.py capture --manifest work/testing__C24757__NRS-484B-250-4__motor_vehicle_driver/execution-manifest.json --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__inoperative_signal_post_stop --output .runtime-work/testing__C24757__NRS-484B-250-4__motor_vehicle_driver-attempt-001 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Remaining GPU/source checks:
- Four installed uncovered governing dark Native heads at entry
- Physical stop line tiles and continuous complete stop
- Earlier completed stop, intersection occupancy and actual yielding
- Corner occlusion, driver sight rays, four original view pixels and duration
- Official signal provenance and cautiousness legal review
