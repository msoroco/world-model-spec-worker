"""Source-bound branch labels for NRS 484B.267(2)(f) and (4).

These labels are requests for distinct Native captures and original-source
review. They do not decide legal compliance from synthetic state.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceState:
    subject_is_other_driver: bool
    source_vehicle_kind: str
    authority_reviewed: bool
    qualifying_flash_reviewed: bool
    subject_approaching_source: bool
    source_moving: bool
    visible_movement: bool
    visible_driver_hand_signal: bool
    source_approaching_subject: bool
    source_stopped: bool
    officer_directed_otherwise: bool


def branch_label(state: SourceState) -> str:
    if state.source_vehicle_kind not in ('authorized_emergency', 'regulatory_agency_official'):
        raise ValueError('Source vehicle kind is outside supplied statute')
    if not state.authority_reviewed or not state.qualifying_flash_reviewed:
        return 'source_review_pending'
    if not state.subject_is_other_driver or not state.subject_approaching_source:
        return 'target_inactive'
    if not (state.source_moving or state.visible_movement or state.visible_driver_hand_signal):
        return 'movement_or_visible_preparation_unproved'
    if state.officer_directed_otherwise:
        return 'officer_direction_exception'
    if state.source_approaching_subject and state.source_stopped:
        raise ValueError('Approaching and stopped alternatives cannot hold together')
    if state.source_approaching_subject:
        return 'approaches_referral_subsection_1'
    if state.source_stopped:
        return 'stops_referral_484B_607'
    return 'trajectory_branch_unproved'
