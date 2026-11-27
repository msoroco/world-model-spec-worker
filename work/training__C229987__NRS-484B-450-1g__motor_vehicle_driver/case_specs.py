"""Exact requested signal-approach engineering cases; no legal outcomes."""
CASES = {
    '25': {'gap_ft':25.0,'activity':'stop','exception':'none'},
    '30': {'gap_ft':30.0,'activity':'stop','exception':'none'},
    '35': {'gap_ft':35.0,'activity':'stop','exception':'none'},
    'stand_25': {'gap_ft':25.0,'activity':'stand','exception':'none'},
    'park_25': {'gap_ft':25.0,'activity':'park','exception':'none'},
    'conflict_25': {'gap_ft':25.0,'activity':'stop','exception':'traffic_conflict'},
    'law_25': {'gap_ft':25.0,'activity':'stop','exception':'other_law'},
    'officer_25': {'gap_ft':25.0,'activity':'stop','exception':'police_direction'},
    'device_25': {'gap_ft':25.0,'activity':'stop','exception':'device_direction'},
}
