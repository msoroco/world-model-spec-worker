"""Exercise 30-second source-only channel reconstruction and material negatives."""
import json
from pathlib import Path
import tempfile

from build import HERE, CASES, POLICIES, build
from derive_channels import derive, sha
from prove_saved import fixture


def prove():
    build()
    positives = []
    negatives = []
    scratch_root = HERE.parents[3] / ".runtime-work"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root, prefix="c10365-channels-") as temp:
        root = Path(temp)
        for suffix in CASES:
            for candidate in POLICIES:
                bundle = HERE / "drafts" / suffix / candidate
                source = root / suffix / candidate
                source.mkdir(parents=True)
                raw, video, review = fixture(bundle, source)
                before = tuple(sha(path) for path in (raw, video, review))
                output = source / "derived"
                receipt = derive(bundle, raw, video, review, output, synthetic=True)
                if receipt["frames"] != 600 or len(receipt["channel_hashes"]) != 9:
                    raise AssertionError("Incomplete reconstructed channels")
                if tuple(sha(path) for path in (raw, video, review)) != before:
                    raise AssertionError("Retained source changed")
                positives.append({"case": suffix, "candidate": candidate,
                                  "frames": receipt["frames"], "channels": 9,
                                  "source_unchanged": True,
                                  "receipt_sha256": sha(output / "receipt.json")})
                try:
                    derive(bundle, raw, video, review, output, synthetic=True)
                except ValueError as exc:
                    if "already exists" not in str(exc):
                        raise
                    negatives.append({"case": suffix, "candidate": candidate,
                                      "mutation": "preexisting_output", "rejected": str(exc)})
                else:
                    raise AssertionError("Accepted preexisting channels")
                injected = source / "channels"
                injected.mkdir()
                try:
                    derive(bundle, raw, video, review, source / "injected-derived",
                           synthetic=True)
                except ValueError as exc:
                    if "Injected channels" not in str(exc):
                        raise
                    negatives.append({"case": suffix, "candidate": candidate,
                                      "mutation": "injected_channels", "rejected": str(exc)})
                else:
                    raise AssertionError("Accepted injected channels")
                injected.rmdir()
                rows = [json.loads(line) for line in raw.read_text().splitlines()]
                rows[1]["native_frame"] += 1
                raw.write_text("".join(json.dumps(row) + "\n" for row in rows))
                try:
                    derive(bundle, raw, video, review, source / "bad-derived", synthetic=True)
                except ValueError as exc:
                    if "join" not in str(exc):
                        raise
                    negatives.append({"case": suffix, "candidate": candidate,
                                      "mutation": "native_frame_join", "rejected": str(exc)})
                else:
                    raise AssertionError("Accepted altered Native frame")
    result = {"format": "c10365-source-channel-proof-v1", "positives": positives,
              "negatives": negatives, "physical_observation_claimed": False}
    (HERE / "source-channel-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return {"positives": len(positives), "negatives": len(negatives)}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
