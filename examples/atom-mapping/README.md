# Mapping law evidence to Core

These examples explain the contract; they are not physical evidence.

For `NRS-484B-400-2a`, the source term `drv.turning` asks whether the driver
actually turned. It is **not** in the pinned Core `atomIds`. A case plan can
map it to a measured route, per-frame position and heading, and a turn-boundary
bracket. `kin.position` and `kin.heading` are valid Core requirements when
their full histories are captured.

`st.one_way_roadway` **is** a Core ontology ID. Its pinned adapter capability
is `absent`, so a package requiring it cannot be ready until an actual native
acquisition and conversion path exists. A two-way roadway annotation alone is
not evidence that the Core value was produced.

Example `case-plan.json` fragment:

```json
{
  "source_observation_mapping": {
    "drv.turning": {
      "evidence": "Measured heading, position and route across the turn interval",
      "channels": ["subject_pose", "subject_heading", "route_brackets"],
      "source_refs": []
    }
  }
}
```

The channel names here are illustrative. The actual package must declare and
capture them, and must map every term in its frozen assignment.
