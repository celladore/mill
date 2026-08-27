import asyncio

import pytest
from fastapi import HTTPException
from PIL import Image
from services.conversion_service import ConversionBusinessLogic
from services.image_service import ImageConverter


def _source_with_exif(path):
    image = Image.new("RGB", (40, 20), color=(20, 120, 180))
    exif = image.getexif()
    exif[315] = "Mill test artist"
    image.save(path, format="JPEG", exif=exif.tobytes())


def test_conversion_resizes_and_strips_metadata_by_default(tmp_path):
    source = tmp_path / "source.jpg"
    output = tmp_path / "output.webp"
    _source_with_exif(source)

    ImageConverter().convert_image(
        source,
        output,
        target_format="webp",
        quality=72,
        max_size=(20, 20),
    )

    with Image.open(output) as converted:
        assert converted.size == (20, 10)
        assert converted.getexif().get(315) is None


def test_conversion_preserves_aspect_ratio_with_only_width_bounded(tmp_path):
    source = tmp_path / "source.jpg"
    output = tmp_path / "output.webp"
    _source_with_exif(source)

    ImageConverter().convert_image(
        source,
        output,
        target_format="webp",
        max_size=(20, 100_000),
    )

    with Image.open(output) as converted:
        assert converted.size == (20, 10)


def test_conversion_can_preserve_metadata_when_explicitly_requested(tmp_path):
    source = tmp_path / "source.jpg"
    output = tmp_path / "output.jpg"
    _source_with_exif(source)

    ImageConverter().convert_image(
        source,
        output,
        target_format="jpeg",
        strip_metadata=False,
    )

    with Image.open(output) as converted:
        assert converted.getexif().get(315) == "Mill test artist"


def test_image_business_logic_validates_quality_and_forwards_advanced_settings(
    monkeypatch,
):
    captured = {}

    async def fake_process(*args, **kwargs):
        captured.update(kwargs)
        return "converted"

    monkeypatch.setattr(
        "services.conversion_service.ImageService.process_image_file", fake_process
    )

    result = asyncio.run(
        ConversionBusinessLogic.convert_image_file(
            b"image",
            "source.png",
            user_id="user-1",
            target_format="webp",
            quality="72",
            max_file_size=1024,
            max_width=1200,
            max_height=800,
            strip_metadata=False,
            vector_colors=12,
            vector_detail=75,
            path_smoothing=40,
            remove_background=True,
            vector_max_dimension=2048,
        )
    )

    assert result == "converted"
    assert captured["quality"] == "72"
    assert captured["max_width"] == 1200
    assert captured["max_height"] == 800
    assert captured["strip_metadata"] is False
    assert captured["vector_colors"] == 12
    assert captured["vector_detail"] == 75
    assert captured["path_smoothing"] == 40
    assert captured["remove_background"] is True
    assert captured["vector_max_dimension"] == 2048

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            ConversionBusinessLogic.convert_image_file(
                b"image",
                "source.png",
                user_id="user-1",
                target_format="webp",
                quality="101",
                max_file_size=1024,
            )
        )
    assert error.value.status_code == 400

    with pytest.raises(HTTPException) as vector_error:
        asyncio.run(
            ConversionBusinessLogic.convert_image_file(
                b"image",
                "source.png",
                user_id="user-1",
                target_format="svg",
                quality="high",
                max_file_size=1024,
                vector_colors=1,
            )
        )
    assert vector_error.value.status_code == 400
    assert vector_error.value.detail == "Vector colors must be between 2 and 32"
