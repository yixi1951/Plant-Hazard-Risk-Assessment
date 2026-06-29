"""上传校验单元测试。"""
import io
import os
import sys

import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.upload_security import (
    detect_image_signature,
    open_validated_image,
    validate_filename,
    validate_upload_bytes,
)


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 128, 0)).save(buf, format="PNG")
    return buf.getvalue()


def test_detect_png_signature():
    data = _png_bytes()
    assert detect_image_signature(data) == "PNG"


def test_reject_php_filename():
    with pytest.raises(ValueError, match="可疑"):
        validate_filename("payload.php")


def test_validate_upload_roundtrip():
    data = _png_bytes()
    out = validate_upload_bytes(data, "leaf.png", max_bytes=1024 * 1024)
    assert out == data
    img, fmt = open_validated_image(data)
    assert img.size == (8, 8)
    assert fmt == "PNG"