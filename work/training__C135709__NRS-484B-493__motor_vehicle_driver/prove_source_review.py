"""CPU source-role proof; synthetic records never establish official authority."""
import hashlib
import json
from pathlib import Path
import tempfile

from source_review import REQUIRED, reviewed_context

ASSIGNMENT = "training__C135709__NRS-484B-493__motor_vehicle_driver"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(folder):
    road = b'<OpenDRIVE name="synthetic-source-role-check" />'
    (folder / "road.xodr").write_bytes(road)
    context = {"assignment_id": ASSIGNMENT, "source_kind": "native_saved_sample",
               "road_id": "1", "map_source_sha256": sha(road)}
    (folder / "road-context.json").write_text(json.dumps(context) + "\n")
    review = folder / "authority-review"
    review.mkdir()
    for name, (claim, _) in REQUIRED.items():
        source = ("Synthetic role-only record for " + name + "\n").encode()
        (review / (name + ".source.txt")).write_bytes(source)
        record = {"assignment_id": ASSIGNMENT, "road_id": "1",
                  "provenance_kind": "synthetic_fixture", "source_sha256": sha(source),
                  "source_title": "Synthetic role-only record", "source_locator": "CPU fixture",
                  "reviewer": "CPU fixture", claim: True}
        (review / (name + ".json")).write_text(json.dumps(record) + "\n")


def rejects(folder, expected):
    try:
        reviewed_context(folder, diagnostic=True)
    except ValueError as error:
        if expected in str(error):
            return
        raise
    raise AssertionError("Unverified source accepted: " + expected)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        prepare(folder)
        assert len(reviewed_context(folder, diagnostic=True)["reviewed_source_hashes"]) == 5
        rejects_nonfixture = False
        try:
            reviewed_context(folder, diagnostic=False)
        except ValueError as error:
            rejects_nonfixture = "Review provenance differs" in str(error)
        assert rejects_nonfixture
        review = folder / "authority-review"
        record = review / "device-authority.json"
        original = record.read_text()
        record.unlink()
        rejects(folder, "Missing required source: authority-review/device-authority.json")
        record.write_text(original)
        (review / "one-way-designation.source.txt").write_text("Changed source\n")
        rejects(folder, "Missing or changed review source: one-way-designation")
        (review / "one-way-designation.source.txt").write_text(
            "Synthetic role-only record for one-way-designation\n")
        wrong = json.loads(record.read_text())
        wrong["device_official"] = False
        record.write_text(json.dumps(wrong) + "\n")
        rejects(folder, "Required activation unverified: device-authority")
    print(json.dumps({"passed": True, "source_roles": sorted(REQUIRED),
                      "negative_checks": ["missing_authority", "changed_designation",
                                          "unverified_official", "synthetic_as_original"],
                      "original_authority_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
