# C147332 red-X source acquisition and Native face source

The selected 90 m OpenDRIVE road is an engineering fixture. It has no claimed
Nevada highway location. The SVG is worker-authored source artwork for a proposed
display face. It is not an imported CARLA/Unreal Blueprint, an official Nevada
signal design, or an observed rendered signal.

## Original-source acquisition

Acquire original local bytes for an exact public-highway site record and an
official overhead lane-control device or as-built record. Record the exact route,
direction, milepost or cross streets, gantry/device identifier, bus approach, and
which lane the device governs. The general [NDOT ATM program page](https://www.dot.nv.gov/safety/active-traffic-management-atm-system)
and [NDOT activation notice](https://www.dot.nv.gov/Home/Components/News/News/4980/395?cftype=9ZV1KO73)
identify real highway corridors and overhead X signals, but do not by themselves
identify this road fixture, a particular gantry, or its bus-facing lane.

Create a local JSON manifest with `site` containing `route`,
`travel_direction`, `milepost_or_cross_streets`, `gantry_or_device_id`,
`bus_approach`, and `governed_lane: red_lane`. Add `documents.highway` and
`documents.official_device`; each contains `local_path` to original bytes,
`citation`, and `acquired_from`. Stage the packet in a new empty directory:

```sh
export TMPDIR="$PWD/.runtime-work"
.venv-cpu/bin/python work/testing__C147332__NRS-484B-307-12b__bus_driver/source-kit/acquire_source_packet.py \
  "$PWD/.runtime-work/c147332-source-manifest.json" \
  "$PWD/.runtime-work/c147332-source-draft"
```

The tool retains both byte streams with SHA-256 and emits a **pending** draft.
An independent reviewer must read the retained originals, confirm the highway,
device, site, direction, lane, and bus-facing join, and document their own identity
and citations before producing a reviewed packet. The reviewer must separately
inspect the actual imported Native asset blueprint, its mutable display-state
attribute, the `red_x` value, and the official-design match. A general program
page cannot be substituted for site-specific evidence. Place the reviewed source
packet under the assignment only after that review; `source_review.validate`
checks its hash-bound form before Native dispatch.

## Proposed Native display face

`red-x-face.svg` contains a black 1024 by 1024 panel and two red diagonal
strokes. `native-red-x-display.json` records the intended `display_state=red_x`
interface and explicitly marks it unimported. A CARLA operator must create the
Unreal asset from reviewed official design material, expose the declared state
on the resulting blueprint, and identify the exact blueprint ID. The existing
`native_driver.spawn_scene` CPU path sets and reads the state before bus spawn;
`native_capture.run_native` checks the actor state every tick. The saved pixel
auditors can verify original camera bytes after capture. None of those CPU checks
establish that the displayed red X is visible, correctly aimed or official.

After importing the actual blueprint into a running CARLA server, check its ID,
mutable display attribute, allowed red-X value and readback:

```sh
.venv-cpu/bin/python work/testing__C147332__NRS-484B-307-12b__bus_driver/source-kit/probe_native_asset.py \
  --blueprint-id static.ACTUAL_IMPORTED_ID \
  --output "$PWD/.runtime-work/c147332-native-asset-probe.json"
```

The probe has a fake-library CPU test, but this host has no `carla` or `unreal`
module, CARLA server, Unreal editor, or imported signal `.uasset`. An actual
probe receipt therefore remains to be produced by the local CARLA operator and
reviewed with original rendered pixels before the selected Native source packet
can identify a real asset.

After obtaining both the staged original-source draft and a real probe receipt,
bind their exact hashes before independent review:

```sh
.venv-cpu/bin/python work/testing__C147332__NRS-484B-307-12b__bus_driver/source-kit/bind_asset_probe.py \
  "$PWD/.runtime-work/c147332-source-draft/draft-context.json" \
  "$PWD/.runtime-work/c147332-native-asset-probe.json" \
  "$PWD/.runtime-work/c147332-source-draft/probe-binding.json"
```

The binding rejects changed originals or an altered probe and remains
`pending_independent_review`. The reviewer must inspect both originals and the
actual imported device, and establish the site/gantry/approach/lane and design
association. The later Native attempt needs a separate original-pixel review.
The binding itself is neither a reviewed source packet nor a physical receipt.

## Convert an independently reviewed binding

The reviewer supplies `review.json` with `format:
worker-red-x-independent-review-v1`, `status: approved`, a nonempty `reviewer`,
SHA-256 fields `source_draft_sha256`, `native_probe_sha256`, and
`probe_binding_sha256`, and true `checks` for `exact_public_highway_and_site`,
`official_device_original`, `bus_facing_and_governed_lane_join`, and
`official_design_matches_imported_asset`. Its `citations` name `highway`,
`official_device`, and `native_display_state`. These are explicit reviewer
findings, not values inferred by the CPU tool.

```sh
.venv-cpu/bin/python work/testing__C147332__NRS-484B-307-12b__bus_driver/source-kit/finalize_reviewed_packet.py \
  "$PWD/.runtime-work/c147332-source-draft/draft-context.json" \
  "$PWD/.runtime-work/c147332-native-asset-probe.json" \
  "$PWD/.runtime-work/c147332-source-draft/probe-binding.json" \
  "$PWD/.runtime-work/c147332-source-draft/review.json" \
  "$PWD/.runtime-work/c147332-source-draft/reviewed.json"
```

The finalizer checks original and intermediate hashes and refuses missing
findings, altered originals, or a repeated output. It cannot establish that
the findings are true. The output must pass `source_review.validate` before
Native dispatch; rendered pixels are reviewed after the actual capture.
