import xml.etree.ElementTree as ET

import pytest
from PIL import Image, ImageDraw
from services.image_service import SvgVectorizer


def test_quantization_and_layer_extraction_are_bounded_and_area_sorted():
    image = Image.new("RGBA", (4, 2), (255, 0, 0, 255))
    image.putpixel((3, 1), (0, 0, 255, 255))

    indexed, palette = SvgVectorizer.quantize(image, colors=2)
    layers = SvgVectorizer.extract_layers(indexed, palette, image.getchannel("A"))

    assert len(palette) <= 2
    assert [area for _color, _mask, area in layers] == [7, 1]


def test_contour_tracing_and_smoothing_emit_closed_vector_paths():
    mask = [True, True, True, True]

    contours = SvgVectorizer.trace_contours(mask, width=2, height=2)

    assert len(contours) == 1
    simplified = SvgVectorizer.simplify_contour(contours[0], tolerance=0)
    assert set(simplified) == {(0, 0), (2, 0), (2, 2), (0, 2)}
    assert " L " in SvgVectorizer.contour_to_path(simplified, smoothing=0)
    assert " Q " in SvgVectorizer.contour_to_path(simplified, smoothing=75)


def test_background_removal_uses_a_dominant_flat_border():
    image = Image.new("RGBA", (8, 8), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 6, 6), fill="red")
    draw.rectangle((3, 3, 4, 4), fill="white")

    result, removed = SvgVectorizer.remove_background(image)

    assert removed is True
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((2, 2)) == (255, 0, 0, 255)
    assert result.getpixel((3, 3)) == (255, 255, 255, 255)


def test_end_to_end_vectorization_generates_parseable_svg(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.svg"
    image = Image.new("RGB", (24, 16), "white")
    ImageDraw.Draw(image).rectangle((4, 4, 18, 12), fill=(20, 120, 180))
    image.save(source)

    result = SvgVectorizer().vectorize(
        source,
        output,
        colors=4,
        detail=80,
        smoothing=50,
        remove_background=True,
        max_dimension=512,
    )

    root = ET.fromstring(output.read_text(encoding="utf-8"))
    paths = root.findall("{http://www.w3.org/2000/svg}path")
    assert root.attrib["viewBox"] == "0 0 24 16"
    assert result.width == 24
    assert result.height == 16
    assert result.colors == 1
    assert result.paths == len(paths) == 1
    assert result.background_removed is True
    assert paths[0].attrib["fill"].startswith("#")


def test_vectorization_bounds_total_pixel_work(tmp_path):
    source = tmp_path / "large.png"
    output = tmp_path / "bounded.svg"
    Image.new("RGB", (16, 16), "red").save(source)
    vectorizer = SvgVectorizer()
    vectorizer.MAX_VECTOR_PIXELS = 64

    result = vectorizer.vectorize(source, output, max_dimension=64)

    assert (result.width, result.height) == (8, 8)


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"colors": 1}, "Vector colors"),
        ({"detail": 0}, "Vector detail"),
        ({"smoothing": 101}, "Path smoothing"),
        ({"max_dimension": 4096}, "Vector maximum dimension"),
    ],
)
def test_vector_settings_are_bounded(tmp_path, settings, message):
    source = tmp_path / "source.png"
    Image.new("RGB", (4, 4), "black").save(source)

    with pytest.raises(ValueError, match=message):
        SvgVectorizer().vectorize(source, tmp_path / "output.svg", **settings)
