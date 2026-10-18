"""Small, locally stored raster uploads; never accept executable SVG/HTML."""
import base64
import binascii
import hashlib
import struct

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_DIMENSION = 4096


def validate_image(payload, max_bytes=MAX_IMAGE_BYTES):
    encoded = payload.get("data", "")
    limit = f"{max_bytes // (1024 * 1024)} MB"
    if not isinstance(encoded, str) or len(encoded) > (max_bytes * 4 // 3 + 8):
        raise ValueError(f"รูปต้องมีขนาดไม่เกิน {limit}")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("ข้อมูลรูปภาพไม่ถูกต้อง") from None
    if not 20 <= len(raw) <= max_bytes:
        raise ValueError(f"รูปต้องมีขนาดไม่เกิน {limit} และเป็นไฟล์ภาพที่สมบูรณ์")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        # Validate chunk framing and checksums; prevents merely renaming another file.
        offset, width, height, ended, image_data = 8, 0, 0, False, False
        while offset + 12 <= len(raw):
            size = struct.unpack(">I", raw[offset:offset + 4])[0]
            kind = raw[offset + 4:offset + 8]
            end = offset + 8 + size
            if end + 4 > len(raw):
                raise ValueError("ไฟล์ PNG ไม่สมบูรณ์")
            if binascii.crc32(raw[offset + 4:end]) & 0xffffffff != struct.unpack(">I", raw[end:end + 4])[0]:
                raise ValueError("ไฟล์ PNG เสียหาย")
            if offset == 8:
                if kind != b"IHDR" or size != 13:
                    raise ValueError("ไฟล์ PNG ไม่ถูกต้อง")
                width, height = struct.unpack(">II", raw[offset + 8:offset + 16])
            if kind == b"IDAT" and size:
                image_data = True
            offset = end + 4
            if kind == b"IEND":
                ended = size == 0 and offset == len(raw)
                break
        if not ended or not image_data or not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION:
            raise ValueError("PNG ต้องสมบูรณ์และมีขนาดไม่เกิน 4096 × 4096")
        mime = "image/png"
    elif raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9"):
        # Walk JPEG segments to find a real start-of-frame with bounded dimensions.
        pos, width, height = 2, 0, 0
        while pos + 4 < len(raw):
            if raw[pos] != 0xff:
                break
            marker = raw[pos + 1]
            if marker == 0xff:
                pos += 1
                continue
            if marker in (0xd8, 0xd9):
                pos += 2
                continue
            size = int.from_bytes(raw[pos + 2:pos + 4], "big")
            if size < 2 or pos + 2 + size > len(raw):
                break
            if marker in (0xc0, 0xc1, 0xc2) and size >= 8:
                height, width = struct.unpack(">HH", raw[pos + 5:pos + 9])
                break
            pos += 2 + size
        if not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION:
            raise ValueError("JPEG ต้องสมบูรณ์และมีขนาดไม่เกิน 4096 × 4096")
        mime = "image/jpeg"
    else:
        raise ValueError("รองรับเฉพาะ PNG หรือ JPEG กรุณาเลือกภาพใหม่")
    return {"id": hashlib.sha256(raw).hexdigest(), "mime": mime, "data": raw}
