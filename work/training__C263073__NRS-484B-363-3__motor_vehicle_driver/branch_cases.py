"""Exact selected school-zone contexts; assertions are source-review targets."""

CASES = {
    'controlled_1': {'turn': False, 'child_actor': True, 'target_exception': None,
                     'context': 'active_prohibition'},
    'controlled_2': {'turn': True, 'child_actor': True, 'target_exception': None,
                     'context': 'active_prohibition'},
    'exception_a': {'turn': True, 'child_actor': False,
                    'target_exception': 'a_no_children', 'context': 'no_children_present'},
    'exception_b': {'turn': True, 'child_actor': True,
                    'target_exception': 'b_not_in_session', 'context': 'non_session_day'},
    'exception_c': {'turn': True, 'child_actor': True,
                    'target_exception': 'c_operation_interval', 'context': 'half_hour_operation_interval'},
    'exception_d': {'turn': True, 'child_actor': True,
                    'target_exception': 'd_operational_beacon_class_hours',
                    'context': 'class_hours_nonflashing_beacon'},
    'exception_e_reference': {'turn': True, 'child_actor': True,
                              'target_exception': None,
                              'context': 'no_operational_beacon_sign_limit_in_effect'},
    'exception_e': {'turn': True, 'child_actor': True,
                    'target_exception': 'e_no_operational_beacon_sign',
                    'context': 'no_operational_beacon_sign_limit_not_in_effect'},
}

FACT_TOPICS = {
    'children_present': ('child_identity', 'child_location'),
    'school_session_day': ('school_session', 'civil_time'),
    'half_hour_operation_interval': ('school_operation', 'civil_time'),
    'beacon_operational': ('beacon_configuration',),
    'class_hours': ('class_hours', 'civil_time'),
    'yellow_lights_flashing': ('beacon_lights',),
    'sign_limit_in_effect': ('zone_sign', 'civil_time'),
}

BASE_FACTS = {'children_present': True, 'school_session_day': True,
              'half_hour_operation_interval': False, 'beacon_operational': True,
              'class_hours': True, 'yellow_lights_flashing': True,
              'sign_limit_in_effect': True}


def expected_facts(case_suffix):
    facts = dict(BASE_FACTS)
    if case_suffix == 'exception_a':
        facts['children_present'] = False
    elif case_suffix == 'exception_b':
        facts['school_session_day'] = False
        facts['half_hour_operation_interval'] = True
        facts['class_hours'] = False
    elif case_suffix == 'exception_c':
        facts['half_hour_operation_interval'] = True
        facts['class_hours'] = False
    elif case_suffix == 'exception_d':
        facts['yellow_lights_flashing'] = False
    elif case_suffix in ('exception_e_reference', 'exception_e'):
        facts['beacon_operational'] = False
        facts['yellow_lights_flashing'] = False
        if case_suffix == 'exception_e':
            facts['sign_limit_in_effect'] = False
    return facts


def check_review(review, case_suffix):
    """Require independent source review to address the exact selected context.

    A reviewer status is a source-bound scenario check, not an automated legal
    verdict. Final legal acceptance remains an independent human decision.
    """
    case = CASES[case_suffix]
    dispositions = review['exception_dispositions']
    target = case['target_exception']
    if target is None:
        if any(item['status'] != 'does_not_apply' for item in dispositions.values()):
            raise ValueError('Active/reference context requires all exceptions absent')
    elif dispositions[target]['status'] != 'applies':
        raise ValueError('Selected exception source review does not support target: ' + target)
    if review.get('case_context') != case['context']:
        raise ValueError('Independent case context differs from selected construction')
    facts = review.get('case_facts')
    if not isinstance(facts, dict) or set(facts) != set(FACT_TOPICS):
        raise ValueError('Seven independent school context facts missing')
    expected = expected_facts(case_suffix)
    for key, topics in FACT_TOPICS.items():
        item = facts[key]
        if not isinstance(item, dict) or type(item.get('value')) is not bool or item['value'] != expected[key]:
            raise ValueError('Selected school context fact differs: ' + key)
        if item.get('source_topics') != list(topics):
            raise ValueError('School context fact source topics differ: ' + key)
        if item.get('source_sha256') != {topic: review['records'][topic]['sha256'] for topic in topics}:
            raise ValueError('School context fact source hashes differ: ' + key)
        if not isinstance(item.get('reviewer_reason'), str) or not item['reviewer_reason'].strip():
            raise ValueError('School context fact reviewer reason missing: ' + key)
    definition = review.get('beacon_definition')
    if not isinstance(definition, dict):
        raise ValueError('Statutory speed-limit-beacon definition review missing')
    if (type(definition.get('yellow_light_count')) is not int or
            definition['yellow_light_count'] < 2 or
            definition.get('flashes_alternately') is not True or
            definition.get('used_with_sign') is not True):
        raise ValueError('Speed-limit-beacon device definition not source supported')
    topics = ('beacon_configuration', 'beacon_lights', 'zone_sign')
    if (definition.get('source_topics') != list(topics) or
            definition.get('source_sha256') !=
            {topic: review['records'][topic]['sha256'] for topic in topics} or
            not isinstance(definition.get('reviewer_reason'), str) or
            not definition['reviewer_reason'].strip()):
        raise ValueError('Speed-limit-beacon definition source binding differs')
    return case
