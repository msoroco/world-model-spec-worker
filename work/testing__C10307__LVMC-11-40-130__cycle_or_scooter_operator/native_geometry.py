"""CPU-checkable candidate alley route and rack envelope for C10307."""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


ALLEY_LENGTH_M = 80.0
ALLEY_HALF_WIDTH_M = 2.0
BICYCLE_HALF_WIDTH_M = 0.45
ROUTE_Y_M = -0.75
RACK_ENVELOPE_XY_M = (-1.2, 2.05, 1.2, 2.65)
ROUTE_START_X_M = -30.0
ROUTE_END_X_M = 30.0


def opendrive_text() -> str:
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C10307 alley engineering candidate" version="1" north="3" south="-3" east="40" west="-40" vendor="worker-candidate"/>
  <road name="single access alley candidate" length="80" id="10307" junction="-1">
    <link/>
    <planView><geometry s="0" x="-40" y="0" hdg="0" length="80"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lateralProfile/>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0"><center><lane id="0" type="none" level="false"/></center>
        <right><lane id="-1" type="driving" level="false"><width sOffset="0" a="4" b="0" c="0" d="0"/></lane></right>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
'''


def validate_geometry(map_path: Path, rack_envelope=RACK_ENVELOPE_XY_M) -> dict:
    data = map_path.read_bytes()
    if data.decode() != opendrive_text():
        raise ValueError("authored alley map differs from checked candidate")
    root = ET.fromstring(data)
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or float(road.attrib["length"]) != ALLEY_LENGTH_M:
        raise ValueError("candidate alley length mismatch")
    geometry = road.find("./planView/geometry")
    lane = road.find("./lanes/laneSection/right/lane")
    width = lane.find("width") if lane is not None else None
    if geometry is None or geometry.find("line") is None or float(geometry.attrib["x"]) != -40 or width is None or float(width.attrib["a"]) != 4.0:
        raise ValueError("candidate alley route geometry mismatch")
    if len(rack_envelope) != 4 or rack_envelope[0] >= rack_envelope[2] or rack_envelope[1] >= rack_envelope[3]:
        raise ValueError("invalid physical rack envelope")
    if rack_envelope[1] <= ALLEY_HALF_WIDTH_M:
        raise ValueError("rack envelope intrudes on bicycle travel surface")
    if rack_envelope[0] > 0 or rack_envelope[2] < 0:
        raise ValueError("rack does not flank the reference route")
    if not (-ALLEY_HALF_WIDTH_M < ROUTE_Y_M - BICYCLE_HALF_WIDTH_M and ROUTE_Y_M + BICYCLE_HALF_WIDTH_M < ALLEY_HALF_WIDTH_M):
        raise ValueError("bicycle body cannot fit in alley")
    if ROUTE_START_X_M < -ALLEY_LENGTH_M / 2 or ROUTE_END_X_M > ALLEY_LENGTH_M / 2:
        raise ValueError("bicycle route extends beyond alley")
    return {"map_sha256": hashlib.sha256(data).hexdigest(), "route_xy_m": [[ROUTE_START_X_M, ROUTE_Y_M], [ROUTE_END_X_M, ROUTE_Y_M]],
            "rack_envelope_xy_m": list(rack_envelope), "rack_visual_asset_verified": False,
            "municipal_jurisdiction_verified": False}


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-map", type=Path)
    parser.add_argument("--check-map", type=Path)
    args = parser.parse_args()
    if args.write_map:
        if args.write_map.exists():
            raise ValueError("refusing to overwrite authored map")
        args.write_map.write_text(opendrive_text())
    if args.check_map:
        print(json.dumps(validate_geometry(args.check_map), sort_keys=True))


if __name__ == "__main__":
    main()
