"""上传与 URL 拉取图片的校验逻辑（供 Flask 与单元测试复用）。"""
from __future__ import annotations

import io
import ipaddress
import os
import re
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

from PIL import Image

FILENAME_BAD_RE = re.compile(r"\.(php|phtml|exe|sh|js|py|bat|cmd|ps1)$", re.IGNORECASE)
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "BMP", "GIF", "TIFF", "WEBP"}


def detect_image_signature(data: bytes) -> Optional[str]:
    if not data:
        return None
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "GIF"
    if data.startswith(b"BM"):
        return "BMP"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return "TIFF"
    return None


def host_resolves_to_private(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return True
            except Exception:
                continue
    except Exception:
        return True
    return False


def validate_filename(filename: str) -> None:
    if FILENAME_BAD_RE.search(filename or ""):
        raise ValueError("上传文件名含可疑扩展名，已被拒绝")


def open_validated_image(data: bytes, source_label: str = "upload") -> Tuple[Image.Image, str]:
    signature = detect_image_signature(data)
    if signature is None:
        raise ValueError("上传内容不是受支持的图片格式")
    if signature not in ALLOWED_IMAGE_FORMATS:
        raise ValueError(f"上传图片格式不支持：{signature}")

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise ValueError("图片文件损坏或格式不正确") from exc

    detected_format = (image.format or "").upper()
    if detected_format == "JPG":
        detected_format = "JPEG"
    if detected_format not in ALLOWED_IMAGE_FORMATS:
        raise ValueError(f"图片格式不支持：{detected_format or 'UNKNOWN'}")

    return image.convert("RGB"), detected_format


def reject_internet_shortcut_prefix(data: bytes) -> None:
    prefix = (data[:40] or b"").lower()
    if prefix.startswith(b"[internetshortcut]") or b"url=" in prefix or prefix.startswith(b"http"):
        raise ValueError("检测到上传内容像是链接/快捷方式，不是图片。")


def enforce_max_bytes(data: bytes, max_bytes: int, label: str = "上传") -> None:
    if data and len(data) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValueError(f"{label}文件过大，最大支持 {mb}MB")


def validate_upload_bytes(data: bytes, filename: str = "", max_bytes: int = 10 * 1024 * 1024) -> bytes:
    validate_filename(filename)
    enforce_max_bytes(data, max_bytes)
    reject_internet_shortcut_prefix(data)
    if detect_image_signature(data) is None:
        raise ValueError("上传内容不是受支持的图片格式")
    _, ext = os.path.splitext((filename or "").lower())
    if ext and ext not in ALLOWED_EXTS:
        pass  # 仍以魔数 + PIL 为准
    return data


def validate_image_url(url: str, max_bytes: int) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 http/https 图片 URL")
    host = parsed.hostname or ""
    if host.lower().startswith("localhost") or host.startswith("127."):
        raise ValueError("拒绝下载内网或本地地址")
    if host_resolves_to_private(host):
        raise ValueError("拒绝下载内网或本地地址")