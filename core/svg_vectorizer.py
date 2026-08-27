"""Deterministic raster-to-SVG vectorization derived from VectorForge's core pipeline."""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from PIL import Image

Point = Tuple[float, float]
Edge = Tuple[Point, Point]


@dataclass(frozen=True)
class VectorizationResult:
    width: int
    height: int
    colors: int
    paths: int
    background_removed: bool


class SvgVectorizer:
    """Bounded five-stage raster-to-SVG converter with no provider dependency."""

    MAX_VECTOR_PIXELS = 1_048_576

    def vectorize(
        self,
        input_path: Path,
        output_path: Path,
        *,
        colors: int = 8,
        detail: int = 60,
        smoothing: int = 50,
        remove_background: bool = False,
        max_dimension: int = 1024,
    ) -> VectorizationResult:
        self._validate_settings(colors, detail, smoothing, max_dimension)
        with Image.open(input_path) as source:
            image = source.convert("RGBA")
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        if image.width * image.height > self.MAX_VECTOR_PIXELS:
            scale = (self.MAX_VECTOR_PIXELS / (image.width * image.height)) ** 0.5
            image = image.resize(
                (
                    max(1, int(image.width * scale)),
                    max(1, int(image.height * scale)),
                ),
                Image.Resampling.LANCZOS,
            )

        background_removed = False
        if remove_background:
            image, background_removed = self.remove_background(image)

        indexed, palette = self.quantize(image, colors)
        layers = self.extract_layers(indexed, palette, image.getchannel("A"))
        tolerance = max(0.0, (100 - detail) / 25.0)
        path_elements: List[str] = []
        for color, mask, _area in layers:
            contours = self.trace_contours(mask, image.width, image.height)
            contours = [self.simplify_contour(points, tolerance) for points in contours]
            path_data = [self.contour_to_path(points, smoothing) for points in contours]
            path_data = [path for path in path_data if path]
            if path_data:
                path_elements.append(
                    f'<path d="{" ".join(path_data)}" fill="{color}" fill-rule="evenodd"/>'
                )

        svg = self.generate_svg(image.width, image.height, path_elements)
        output_path.write_text(svg, encoding="utf-8")
        return VectorizationResult(
            width=image.width,
            height=image.height,
            colors=len(layers),
            paths=len(path_elements),
            background_removed=background_removed,
        )

    @staticmethod
    def _validate_settings(
        colors: int, detail: int, smoothing: int, max_dimension: int
    ) -> None:
        if not 2 <= colors <= 32:
            raise ValueError("Vector colors must be between 2 and 32")
        if not 1 <= detail <= 100:
            raise ValueError("Vector detail must be between 1 and 100")
        if not 0 <= smoothing <= 100:
            raise ValueError("Path smoothing must be between 0 and 100")
        if not 64 <= max_dimension <= 2048:
            raise ValueError("Vector maximum dimension must be between 64 and 2048")

    @staticmethod
    def remove_background(
        image: Image.Image, threshold: int = 20
    ) -> Tuple[Image.Image, bool]:
        """Remove a flat border-connected background without guessing from interior content."""
        pixels = image.load()
        width, height = image.size
        border = []
        for x in range(width):
            border.extend((pixels[x, 0], pixels[x, height - 1]))
        for y in range(1, height - 1):
            border.extend((pixels[0, y], pixels[width - 1, y]))
        opaque = [pixel[:3] for pixel in border if pixel[3] >= 10]
        if not opaque:
            return image, False
        background, count = Counter(opaque).most_common(1)[0]
        if count / len(opaque) < 0.5:
            return image, False

        result = image.copy()
        output = result.load()
        candidates = deque(
            [(x, 0) for x in range(width)]
            + [(x, height - 1) for x in range(width)]
            + [(0, y) for y in range(1, height - 1)]
            + [(width - 1, y) for y in range(1, height - 1)]
        )
        visited = set()
        removed = 0
        while candidates:
            x, y = candidates.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            pixel = output[x, y]
            if (
                pixel[3] < 10
                or max(abs(pixel[index] - background[index]) for index in range(3))
                > threshold
            ):
                continue
            output[x, y] = (pixel[0], pixel[1], pixel[2], 0)
            removed += 1
            for next_x, next_y in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if 0 <= next_x < width and 0 <= next_y < height:
                    candidates.append((next_x, next_y))
        return result, removed > 0

    @staticmethod
    def _pixel_values(image: Image.Image) -> List[int]:
        flattened = getattr(image, "get_flattened_data", None)
        return list(flattened() if flattened else image.getdata())

    @staticmethod
    def quantize(image: Image.Image, colors: int) -> Tuple[Image.Image, Dict[int, str]]:
        """Quantize opaque RGB pixels while retaining the source alpha channel."""
        rgb = Image.new("RGB", image.size, "white")
        rgb.paste(image.convert("RGB"), mask=image.getchannel("A"))
        indexed = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        raw_palette = indexed.getpalette() or []
        used = sorted(set(SvgVectorizer._pixel_values(indexed)))
        palette = {
            index: "#{:02x}{:02x}{:02x}".format(*raw_palette[index * 3 : index * 3 + 3])
            for index in used
        }
        return indexed, palette

    @staticmethod
    def extract_layers(
        indexed: Image.Image, palette: Dict[int, str], alpha: Image.Image
    ) -> List[Tuple[str, List[bool], int]]:
        """Split the quantized image into deterministic, area-sorted color masks."""
        indexes = SvgVectorizer._pixel_values(indexed)
        alpha_values = SvgVectorizer._pixel_values(alpha)
        layers = []
        for index, color in palette.items():
            mask = [
                alpha_value >= 10 and pixel_index == index
                for pixel_index, alpha_value in zip(indexes, alpha_values)
            ]
            area = sum(mask)
            if area:
                layers.append((color, mask, area))
        return sorted(layers, key=lambda layer: (-layer[2], layer[0]))

    @staticmethod
    def trace_contours(
        mask: Sequence[bool], width: int, height: int
    ) -> List[List[Point]]:
        """Trace directed pixel-boundary edges into closed contour loops."""
        edges: List[Edge] = []

        def filled(x: int, y: int) -> bool:
            return 0 <= x < width and 0 <= y < height and mask[y * width + x]

        for y in range(height):
            for x in range(width):
                if not filled(x, y):
                    continue
                if not filled(x, y - 1):
                    edges.append(((x, y), (x + 1, y)))
                if not filled(x + 1, y):
                    edges.append(((x + 1, y), (x + 1, y + 1)))
                if not filled(x, y + 1):
                    edges.append(((x + 1, y + 1), (x, y + 1)))
                if not filled(x - 1, y):
                    edges.append(((x, y + 1), (x, y)))

        outgoing: Dict[Point, List[Point]] = defaultdict(list)
        for start, end in edges:
            outgoing[start].append(end)
        for ends in outgoing.values():
            ends.sort(reverse=True)

        contours: List[List[Point]] = []
        while outgoing:
            start = min(outgoing)
            current = start
            contour = [start]
            while True:
                ends = outgoing.get(current)
                if not ends:
                    break
                next_point = ends.pop()
                if not ends:
                    del outgoing[current]
                current = next_point
                if current == start:
                    break
                contour.append(current)
            if current == start and len(contour) >= 4:
                contours.append(contour)
        return contours

    @classmethod
    def simplify_contour(cls, points: Sequence[Point], tolerance: float) -> List[Point]:
        points = cls._remove_collinear(list(points))
        if tolerance <= 0 or len(points) < 4:
            return points

        # Ramer-Douglas-Peucker operates on an open line. Split this closed
        # contour into two open arcs, then join them without duplicate ends.
        split_index = max(
            range(1, len(points)),
            key=lambda index: hypot(
                points[index][0] - points[0][0],
                points[index][1] - points[0][1],
            ),
        )
        first_arc = cls._douglas_peucker(points[: split_index + 1], tolerance)
        second_arc = cls._douglas_peucker(points[split_index:] + [points[0]], tolerance)
        return first_arc[:-1] + second_arc[:-1]

    @staticmethod
    def _remove_collinear(points: List[Point]) -> List[Point]:
        if len(points) < 3:
            return points
        result = []
        for index, point in enumerate(points):
            previous = points[index - 1]
            following = points[(index + 1) % len(points)]
            if (point[0] - previous[0]) * (following[1] - point[1]) != (
                point[1] - previous[1]
            ) * (following[0] - point[0]):
                result.append(point)
        return result

    @classmethod
    def _douglas_peucker(cls, points: Sequence[Point], tolerance: float) -> List[Point]:
        if len(points) < 3:
            return list(points)
        start, end = points[0], points[-1]
        distances = [cls._line_distance(point, start, end) for point in points[1:-1]]
        if not distances or max(distances) <= tolerance:
            return [start, end]
        index = distances.index(max(distances)) + 1
        left = cls._douglas_peucker(points[: index + 1], tolerance)
        right = cls._douglas_peucker(points[index:], tolerance)
        return left[:-1] + right

    @staticmethod
    def _line_distance(point: Point, start: Point, end: Point) -> float:
        dx, dy = end[0] - start[0], end[1] - start[1]
        if dx == 0 and dy == 0:
            return hypot(point[0] - start[0], point[1] - start[1])
        numerator = abs(
            dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0]
        )
        return numerator / hypot(dx, dy)

    @staticmethod
    def contour_to_path(points: Sequence[Point], smoothing: int) -> str:
        if len(points) < 3:
            return ""

        def number(value: float) -> str:
            return f"{value:.2f}".rstrip("0").rstrip(".")

        if smoothing < 25:
            commands = [f"M {number(points[0][0])} {number(points[0][1])}"]
            commands.extend(f"L {number(x)} {number(y)}" for x, y in points[1:])
            return " ".join(commands) + " Z"

        weight = min(0.75, smoothing / 133.0)
        start_midpoint = (
            points[0][0] * (1 - weight) + points[-1][0] * weight,
            points[0][1] * (1 - weight) + points[-1][1] * weight,
        )
        commands = [f"M {number(start_midpoint[0])} {number(start_midpoint[1])}"]
        for index, point in enumerate(points):
            following = points[(index + 1) % len(points)]
            midpoint = (
                following[0] * weight + point[0] * (1 - weight),
                following[1] * weight + point[1] * (1 - weight),
            )
            commands.append(
                f"Q {number(point[0])} {number(point[1])} {number(midpoint[0])} {number(midpoint[1])}"
            )
        return " ".join(commands) + " Z"

    @staticmethod
    def generate_svg(width: int, height: int, paths: Iterable[str]) -> str:
        body = "\n  ".join(paths)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">\n  {body}\n</svg>\n'
        )
