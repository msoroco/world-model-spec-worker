"""Draft source-bound outputs for the two remaining statutory dispositions.

These are engineering observations. The preceding subsection's legal yield
condition and actual Native motion remain for original review.
"""


def measure_priority_requirement(observed):
    return {'value': observed, 'method': 'measure_priority_requirement',
            'sources': {'native_samples.jsonl': observed['native_samples_sha256'],
                        'road.xodr': observed['road_sha256']}}


def measure_prior_yield_antecedent(observed):
    value = {'prior_stopped_frames': observed['entrant_prior_stopped_frames'],
             'about_to_enter_first_frame': observed['about_to_enter_first_frame'],
             'lawful_prior_yield_verified': False}
    return {'value': value, 'method': 'measure_prior_yield_antecedent',
            'sources': {'native_samples.jsonl': observed['native_samples_sha256'],
                        'road.xodr': observed['road_sha256']}}


def measure_entrant_entry_phase(observed, rows):
    crossing = [i for i, row in enumerate(rows) if -7 <= row['entrant']['x_m'] <= 7]
    if not crossing or crossing != list(range(min(crossing), max(crossing) + 1)):
        raise ValueError('Contiguous entrant crossing source absent')
    value = {'about_to_enter_first_frame': observed['about_to_enter_first_frame'],
             'crossing_first_frame': crossing[0], 'crossing_last_frame': crossing[-1],
             'crossing_observed': True,
             'physical_or_legal_timing_verified': False}
    return {'value': value, 'method': 'measure_entrant_entry_phase',
            'sources': {'native_samples.jsonl': observed['native_samples_sha256'],
                        'road.xodr': observed['road_sha256']}}
