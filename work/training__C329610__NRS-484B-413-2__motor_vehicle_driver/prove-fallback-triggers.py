"""Exercise all three measured triggers on synthetic source rows."""
import hashlib
import json
from pathlib import Path
from native.fallback_triggers import evaluate

HERE = Path(__file__).resolve().parent
OUT = HERE / "signal-fixtures"


def write(path, rows):
    raw = b"".join((json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode() for r in rows)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main():
    manifest = json.loads((HERE / "native-construction-manifest.json").read_text())
    rows = [json.loads(line) for line in (OUT / "at_100_ft.jsonl").read_text().splitlines()]
    base_path = OUT / "trigger-base.jsonl"
    digest = write(base_path, rows)
    args = {"expected_sha256": digest, "source_kind": "synthetic_cpu_fixture",
            "map_sha256": manifest["map_sha256"]}
    base = evaluate(base_path, **args)
    assert not any(base[f"fallback{i}"] for i in (1, 2, 3))
    positives = {}
    for name, alter in (("fallback1", None),
                        ("fallback2", lambda r: r.__setitem__("route_error_m", .5)),
                        ("fallback3", lambda r: r.__setitem__("signal_visible", False))):
        changed = [dict(r) for r in rows]
        if name == "fallback1":
            # A distinct short-runway positive is the existing 310-foot capture.
            source = OUT / "above_300_ft.jsonl"
            source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
        else:
            first = next(i for i, r in enumerate(changed) if r["signal"] == "left")
            if name == "fallback2":
                alter(changed[first + 10])
            else:
                for r in changed[first:first + 20]:
                    alter(r)
            source = OUT / (name + "-positive.jsonl")
            source_digest = write(source, changed)
        observed = evaluate(source, expected_sha256=source_digest,
                            source_kind="synthetic_cpu_fixture", map_sha256=manifest["map_sha256"])
        assert observed[name] and not observed["dispatchable_observation"]
        observed["source_path"] = str(source.relative_to(HERE.parent.parent))
        positives[name] = observed
    try:
        evaluate(base_path, expected_sha256="0" * 64, source_kind="synthetic_cpu_fixture",
                 map_sha256=manifest["map_sha256"])
    except ValueError:
        pass
    else:
        raise AssertionError("changed source hash accepted")
    try:
        evaluate(base_path, expected_sha256=digest, source_kind="authored_request",
                 map_sha256=manifest["map_sha256"])
    except ValueError:
        pass
    else:
        raise AssertionError("authored request accepted as observation")
    base["source_path"] = str(base_path.relative_to(HERE.parent.parent))
    summary = {"format":"c329610-413-2-trigger-proof-v1", "base":base,
               "synthetic_positives":positives,"changed_hash_rejected":True,
               "authored_request_rejected":True,"original_native_observed":False}
    (HERE / "fallback-trigger-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({"base_negative":True,"positive_triggers":list(positives),
                      "changed_hash_rejected":True,"authored_request_rejected":True}))


if __name__ == "__main__":
    main()
