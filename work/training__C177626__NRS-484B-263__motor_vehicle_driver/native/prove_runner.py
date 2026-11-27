"""CPU check of exact Native entry cases and four candidate designs."""

from runner import CANDIDATES, CASE_PREFIX, cameras, check

assert [(view["width"], view["height"]) for view in cameras()] == [
    (1920, 1080), (1280, 720), (1280, 720), (1280, 720)
]


def reject(case_id, candidate_id, phrase):
    try:
        check(case_id, candidate_id)
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


for suffix, policy in (("a", "earlier_yield"), ("b", "later_yield")):
    for candidate_id in CANDIDATES:
        proposal = check(CASE_PREFIX + suffix, candidate_id)
        assert proposal["policy"] == policy
        assert proposal["duration_s"] == 30 and proposal["rate_hz"] == 20
        assert len(proposal["camera_views"]) == 4
        assert not proposal["native_original_present"]
        assert not proposal["physical_success_claimed"]
reject(CASE_PREFIX + "exit", "near_70", "exact selected entry case")
reject(CASE_PREFIX + "a", "unknown", "four distinct source candidates")
print("PASS: exact entry A/B Native draft, four candidate designs each, 2 negatives")
