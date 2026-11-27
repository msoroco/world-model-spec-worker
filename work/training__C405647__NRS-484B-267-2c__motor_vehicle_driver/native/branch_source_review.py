"""Require original, frame-bound source review for the extra law branches.

Native bone pose is a requested proxy. It cannot itself establish that the
emergency vehicle's driver signaled or that a law enforcement officer directed
the ego driver. Those links require independent original-source annotation.
"""


def validate(exact, review, observed):
    variant = exact.get("variant")
    if variant is None:
        return {"branch_review_required": False}
    if review.get("review_kind") != "original_source_review" or not review.get("reviewer"):
        raise ValueError("Independent original branch reviewer required")
    field = "source_driver_proxy" if variant == "visible_driver_hand_signal" else "officer_actor"
    annotations = review.get("frame_annotations")
    if not isinstance(annotations, list) or len(annotations) != len(observed):
        raise ValueError("Frame-bound branch review missing")
    actor_id = observed[150].get("indication_native_readback", {}).get(field, {}).get("native_actor_id")
    if type(actor_id) is not int or review.get("indication_actor_native_id") != actor_id:
        raise ValueError("Branch source review does not bind original Native actor")
    if variant == "visible_driver_hand_signal":
        if (review.get("source_driver_identity") != "same_emergency_vehicle_driver" or
                not review.get("source_driver_identity_source") or
                not review.get("hand_signal_source")):
            raise ValueError("Source-driver hand signal identity review missing")
        flag = "hand_signal_visible"
    elif variant == "officer_directed_otherwise":
        if (review.get("officer_identity") != "law_enforcement_officer" or
                not review.get("officer_identity_source") or
                not review.get("officer_direction_source") or
                review.get("officer_direction_present") is not True or
                review.get("officer_direction_applies_to_ego") is not True):
            raise ValueError("Applicable law-enforcement direction review missing")
        flag = "officer_direction_visible"
    else:
        raise ValueError("Unknown branch review variant")
    if not any(note.get(flag) is True and note.get("source_native_frame") == observed[index].get("native_frame")
               for index, note in enumerate(annotations) if 150 <= index <= 199):
        raise ValueError("No frame-bound visible branch indication in original source review")
    return {"branch_review_required": True, "variant": variant,
            "indication_actor_native_id": actor_id,
            "original_pixel_visibility_claimed_by_worker": False}
