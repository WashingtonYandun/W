"""Small compositional programs with a model independent of the compiler."""
import random


def generate_readiness_case(seed):
    rng = random.Random(seed)
    samples = [(rng.choice([True, False]), rng.randint(-20, 20), rng.choice([True, False])) for _ in range(6)]
    source = ['enum Event { Data(tuple[bool, int]), Empty }',
              'fn classify(value: tuple[Event, bool]) -> int {',
              'match value {',
              '(Event.Data((true, number)), true) => number + 1,',
              '(Event.Data((flag, number)), _) => number,',
              '(Event.Empty, _) => -1',
              '}\n}']
    expected = []
    for flag, number, active in samples:
        source.append(f'print(classify((Event.Data(({str(flag).lower()}, {number})), {str(active).lower()})))')
        expected.append(str(number + 1 if flag and active else number))
    source.append('print(classify((Event.Empty, true)))')
    expected.append('-1')
    captured = rng.randint(1, 99)
    failed = rng.choice([True, False])
    source.extend([f'let captured = {captured}',
                   f'let produce: fn() -> int ! str = || -> int ! str {{ if {str(failed).lower()} {{ Err("bad") }} else {{ Ok(captured) }} }}',
                   'print(produce() else error { len(error) })',
                   'let mut original = [captured, 2]',
                   'let snapshot = original',
                   'original[0] = classify((Event.Data((true, captured)), true))',
                   'print(snapshot, original)'])
    expected.append(str(3 if failed else captured))
    expected.append(f'[{captured}, 2] [{captured + 1}, 2]')
    return '\n'.join(source) + '\n', '\n'.join(expected) + '\n'
