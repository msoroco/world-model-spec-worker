"""Write the exact OpenDRIVE engineering candidate used by all four drafts."""
from pathlib import Path
from native_construction import candidate_opendrive
from candidate_map_contract import check_fixed_map


if __name__ == '__main__':
    path = Path(__file__).resolve().parent / 'candidate-red-x-road.xodr'
    path.write_text(candidate_opendrive())
    print(check_fixed_map(path))
