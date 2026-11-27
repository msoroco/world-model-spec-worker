"""CPU checks of prospective restricted-zone OpenDRIVE geometry."""

from __future__ import annotations

import json

from geometry import check, open_drive


def reject(xml: str) -> str:
    try:
        check(xml)
    except (ValueError, AttributeError, KeyError) as exc:
        return str(exc)
    raise AssertionError("accepted altered restricted-zone construction")


def prove() -> dict:
    xml = open_drive()
    positive = check(xml)
    assert positive["requested_zone_bounds_m"] == [0.0, -4.0, 10.0, -1.0]
    assert positive["official_authority_verified"] is False
    negatives = {
        "wrong_road": reject(xml.replace('road id="1"', 'road id="9"')),
        "wrong_sign": reject(xml.replace('subtype="restricted_purpose"',
                                         'subtype="general_parking"')),
        "wrong_lane": reject(xml.replace('a="2.8"', 'a="4.0"', 1)),
        "missing_sign": reject(xml.replace('id="510"', 'id="511"')),
    }
    return {"format": "restricted-zone-geometry-cpu-proof-v1",
            "positive": positive, "negative_rejections": negatives,
            "original_native_observed": False}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
