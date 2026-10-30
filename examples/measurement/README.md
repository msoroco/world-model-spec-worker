# Case-specific measurement examples

`geometry.py` shows two calculations the v4 return left to local review:

- For 400-2a, calculate signed centerline distances for **every body vertex**
  at the original approach frames. Preserve the verified road direction and
  public-way context separately; do not turn the sign of one sample into a
  legal verdict.
- For 257-1, examine multiple original driver viewpoint samples and report
  the point closest to the intersection among samples with a clear ray. Record
  spacing/resolution and source frames. A sampled result does not prove a
  continuous statutory nearest point or rendered pixel visibility.

In a package, name the actual finalizer function in each selected requirement's
measurement contract. The positive fixture must supply the referenced geometry
or ray packet and yield a concrete output value. The negative fixture removes
that case-specific packet, and the finalizer must raise `Missing required
source: <path>`. These examples contain no CARLA run or legal label.

Example contract row for the first selected disposition:

```json
{"disposition_index":0,"requirement":"Approach relative to centerline","source":"law witness","kind":"measured","method":"centerline_offset","value_type":"object","output_key":"approach_centerline_geometry","inputs":["road_geometry.json","body_vertices.jsonl"]}
```

The matching report value is
`{"method":"centerline_offset","value":{"minimum_m":-2,"maximum_m":1},"sources":{"road_geometry.json":"<actual SHA-256>","body_vertices.jsonl":"<actual SHA-256>"}}`.
The fixture recipe adds those two text files to the pinned shared fixture.
Remove `road_geometry.json` for the negative run and require the finalizer to
raise `Missing required source: road_geometry.json`.
