"""Engineering maneuver completion from original parking rows, never law labels."""
from __future__ import annotations

from parking import SourceError, measure_original_history


def evaluate(rows, expected):
    try:
        observed = measure_original_history(rows, expected)
    except (SourceError, KeyError, TypeError, ValueError) as error:
        return {'physical_checks': {'maneuver': {
            'status': 'unverified', 'method': 'original 20 Hz halt and footprint audit',
            'sources': ['original actor rows', 'reviewed governed polygon'],
            'reason': str(error)}}, 'maneuver_completed': False,
            'realized_observables': {}, 'legal_judgment': None}
    completed = observed['halt_inside_frames'] >= 100
    return {'physical_checks': {'maneuver': {
        'status': 'met' if completed else 'not_met',
        'method': 'at least 100 original stationary halt frames with full body footprint inside reviewed polygon',
        'sources': ['original actor rows', 'reviewed governed polygon']}},
        'maneuver_completed': completed,
        'realized_observables': {'halt_inside_frames': observed['halt_inside_frames'],
                                 'effective_prohibition_during_halt_frames': observed['effective_prohibition_during_halt_frames'],
                                 'exception_source_during_halt_frames': observed['exception_source_during_halt_frames']} if completed else {},
        'legal_judgment': None}


class Lifecycle:
    EVENTS = ('capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started')

    def __init__(self):
        self.events = []

    def record(self, event):
        if len(self.events) >= len(self.EVENTS) or event != self.EVENTS[len(self.events)]:
            raise ValueError('Native ownership lifecycle order changed')
        self.events.append(event)

    def complete(self):
        if tuple(self.events) != self.EVENTS:
            raise ValueError('saved processing precedes Native ownership release')
        return {'events': list(self.events), 'exit_code': 0}
