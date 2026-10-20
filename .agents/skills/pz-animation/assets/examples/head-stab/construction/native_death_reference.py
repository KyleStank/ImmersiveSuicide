"""Narrow sampler for the installed Zombie_Death text-X construction reference."""

import re
from pathlib import Path

from mathutils import Matrix, Quaternion, Vector

NUMBER = r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?'
BASIS = Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0))).to_4x4()


def closing_brace(text, opening):
    depth = 1
    cursor = opening + 1
    while depth:
        if text[cursor] == '{':
            depth += 1
        elif text[cursor] == '}':
            depth -= 1
        cursor += 1
    return cursor - 1


def row_matrix(values):
    rows = [values[index:index + 4] for index in range(0, 16, 4)]
    return Matrix(rows).transposed()


def key_value(values, rotation):
    if rotation:
        # DirectX rotation keys use the opposite quaternion convention.
        return Quaternion(values).conjugated()
    return Vector(values)


class NativeDeath:
    def __init__(self, path):
        text = Path(path).read_text(encoding='utf-8-sig')
        self.parents = {}
        self.rest = {}
        spans = []
        for match in re.finditer(r'(?m)^\s*Frame\s+(\w+)\s*\{', text):
            end = closing_brace(text, match.end() - 1)
            parent = next(
                (
                    name
                    for start, finish, name in reversed(spans)
                    if start < match.start() < finish
                ),
                None,
            )
            name = match[1]
            self.parents[name] = parent
            block = text[match.end():end]
            transform = re.search(r'^\s*FrameTransformMatrix\s*\{([^}]+)\}', block)
            values = [float(value) for value in re.findall(NUMBER, transform[1])]
            self.rest[name] = row_matrix(values)
            spans.append((match.start(), end, name))

        self.bind = {}
        for match in re.finditer(r'(?m)^\s*SkinWeights\s*\{([^}]+)\}', text):
            name = re.search(r'"([^"]+)"', match[1])[1]
            numbers = [
                float(value)
                for value in re.findall(NUMBER, match[1].split(';', 1)[1])
            ]
            offset = row_matrix(numbers[-16:])
            self.bind[name] = self.convert(offset.inverted())

        tick_match = re.search(r'(?m)^AnimTicksPerSecond\s*\{\s*(\d+)', text)
        self.ticks_per_second = int(tick_match[1])
        self.channels = {}
        for match in re.finditer(r'(?m)^\s*Animation\s*\{\s*\{\s*(\w+)\s*\}', text):
            opening = text.index('{', match.start())
            block = text[opening + 1:closing_brace(text, opening)]
            channel = {}
            for key_match in re.finditer(r'AnimationKey\s+\w+\s*\{([^}]+)\}', block):
                key_type = int(re.match(r'\s*(\d+)', key_match[1])[1])
                keys = []
                for entry in re.finditer(r'(\d+);(\d+);([^;]+);;', key_match[1]):
                    values = [float(value) for value in entry[3].split(',')]
                    keys.append((int(entry[1]), values))
                channel[key_type] = keys
            self.channels[match[1]] = channel
        self.duration = max(
            time
            for channel in self.channels.values()
            for keys in channel.values()
            for time, values in keys
        )

    @staticmethod
    def convert(matrix):
        # Convert the native Y-up coordinates into the rig's Z-up units.
        result = BASIS @ matrix @ BASIS
        result.translation *= 100
        return result

    @staticmethod
    def interpolate(keys, tick, rotation=False):
        if tick <= keys[0][0]:
            return key_value(keys[0][1], rotation)
        for (start, left), (end, right) in zip(keys, keys[1:]):
            if tick <= end:
                amount = (tick - start) / (end - start)
                first = key_value(left, rotation)
                second = key_value(right, rotation)
                if rotation:
                    return first.slerp(second, amount)
                return first.lerp(second, amount)
        return key_value(keys[-1][1], rotation)

    def pose(self, frame):
        tick = frame * self.ticks_per_second / 30
        world = {}
        for name, rest in self.rest.items():
            local = rest.copy()
            channel = self.channels.get(name)
            if channel:
                location, rotation, scale = rest.decompose()
                if 0 in channel:
                    rotation = self.interpolate(channel[0], tick, rotation=True)
                if 1 in channel:
                    scale = self.interpolate(channel[1], tick)
                if 2 in channel:
                    location = self.interpolate(channel[2], tick)
                local = Matrix.LocRotScale(location, rotation, scale)
            parent = self.parents[name]
            if parent:
                world[name] = world[parent] @ local
            else:
                world[name] = local
        return {name: self.convert(matrix) for name, matrix in world.items()}


if __name__ == '__main__':
    raise RuntimeError(
        'Construction reference only. Import from an adapted Blender authoring script.'
    )
