"""S20 Done-when: PNG integrity/size, reviewed hashes, and README image links.

Run from the repository root: python3 docs/img/check_assets.py
The privacy review is visual and recorded in capture-manifest.json; this script
checks that the reviewed files have not changed. It does not infer privacy from pixels.
"""

import binascii
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
IMAGES = Path(__file__).resolve().parent
EXPECTED = (
    "01-upload.png", "02-progress.png", "03-units.png", "04-functions.png",
    "05-conflicts.png", "06-source.png", "07-conclusion.png", "architecture.png",
)


def check_png(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "invalid PNG signature"
    assert len(data) <= 500_000, f"{len(data)} bytes exceeds 500 KB"
    pos, idat, dimensions, ended = 8, bytearray(), None, False
    while pos < len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        crc = struct.unpack_from(">I", data, pos + 8 + length)[0]
        assert binascii.crc32(kind + body) & 0xFFFFFFFF == crc, "bad chunk CRC"
        if kind == b"IHDR":
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            assert width > 0 and height > 0 and compression == filtering == interlace == 0
            dimensions = width, height, depth, colour
        elif kind == b"IDAT":
            idat.extend(body)
        elif kind == b"IEND":
            ended = True
            assert pos + length + 12 == len(data), "trailing data"
            break
        # No embedded text, camera metadata, or local filenames in shipped images.
        assert kind not in (b"tEXt", b"zTXt", b"iTXt", b"eXIf"), "unexpected metadata"
        pos += length + 12
    assert ended and dimensions is not None, "incomplete PNG"
    width, height, depth, colour = dimensions
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    row_bytes = (width * depth * channels + 7) // 8
    pixels = zlib.decompress(idat)
    assert len(pixels) == height * (row_bytes + 1), "incomplete pixel data"
    assert all(pixels[i] <= 4 for i in range(0, len(pixels), row_bytes + 1)), "invalid row filter"
    return len(data), width, height, hashlib.sha256(data).hexdigest()


def image_links(markdown):
    """Local inline/reference Markdown and HTML images used in the README."""
    links = re.findall(r"!\[[^\]]*\]\(\s*<?([^\s)>]+)", markdown)
    links += re.findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)", markdown, re.I)
    refs = dict(re.findall(r"^\s*\[([^\]]+)\]:\s*<?([^\s>]+)", markdown, re.M))
    for label, ref in re.findall(r"!\[([^\]]*)\]\[([^\]]*)\]", markdown):
        links.append(refs.get(ref or label, "MISSING_REFERENCE"))
    return links


def main():
    failures = []
    manifest_path = IMAGES / "capture-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    reviewed = manifest.get("visually_reviewed_sha256", {})
    names = sorted(set(EXPECTED) | {path.name for path in IMAGES.glob("*.png")})
    for name in names:
        try:
            size, width, height, digest = check_png(IMAGES / name)
            assert reviewed.get(name) == digest, "visual review missing or file changed"
            print(f"OK {name}: {width}x{height}, {size} bytes; reviewed")
        except (OSError, AssertionError, ValueError, KeyError, struct.error, zlib.error) as exc:
            failures.append(f"{name}: {exc}")

    readme = ROOT / "README.md"
    links = image_links(readme.read_text(encoding="utf-8"))
    if not links:
        failures.append("README: no image links yet (S18 pending)")
    linked_names = set()
    for link in links:
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc:
            failures.append(f"README: external image needs separate verification: {link}")
            continue
        path = (ROOT / unquote(parsed.path).lstrip("/")).resolve()
        try:
            path.relative_to(ROOT)
            assert path.is_file(), "file is missing"
            if path.suffix.lower() == ".png":
                check_png(path)
            linked_names.add(path.name)
        except (OSError, AssertionError, ValueError, KeyError, struct.error, zlib.error) as exc:
            failures.append(f"README {link}: {exc}")
    if links:
        missing = set(EXPECTED) - linked_names
        if missing:
            failures.append("README: missing expected images: " + ", ".join(sorted(missing)))
    print(f"README image links: {len(links)}")
    if failures:
        for failure in failures:
            print("FAIL " + failure)
        print("DONE-WHEN: NOT READY")
        return 1
    print("DONE-WHEN: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
