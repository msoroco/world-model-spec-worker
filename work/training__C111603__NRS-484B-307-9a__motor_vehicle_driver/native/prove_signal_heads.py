"""CPU checks for fail-closed authored head identity and state readback."""
import json
from signal_heads import resolve, sample


class Actor:
    type_id = 'traffic.traffic_light'

    def __init__(self, actor_id, opendrive_id, state):
        self.id = actor_id
        self.op = opendrive_id
        self.state = state

    def get_opendrive_id(self):
        return self.op

    def get_state(self):
        return self.state


def rejected(actors):
    try:
        red, arrow = resolve(actors)
        sample(red, arrow)
    except ValueError:
        return True
    return False


def main():
    red = Actor(1001, '601', 'TrafficLightState.Red')
    arrow = Actor(1002, '1603', 'TrafficLightState.Green')
    selected = resolve([arrow, Actor(5, 'other', 'Red'), red])
    assert selected == (red, arrow)
    values = sample(*selected)
    assert values['red']['source'] == values['arrow']['source'] == 'native_readback'
    negatives = [
        [red], [arrow],
        [red, Actor(1003, '601', 'Red'), arrow],
        [red, Actor(1001, '1603', 'Green')],
        [red, Actor(1002, '1603', 'Yellow')],
        [Actor(1001, '601', 'Green'), arrow],
    ]
    assert all(rejected(group) for group in negatives)
    return {'passed': True, 'positives': 1, 'negative_rejections': len(negatives),
            'physical_native_execution': False, 'signal_pixels_verified': False}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
