from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "static" / "assets" / "app"
SHELL_ASSETS = ROOT / "mobile-app-shell" / "assets"


def blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def put_px(pixels: list[list[tuple[int, int, int, int]]], x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if 0 <= y < len(pixels) and 0 <= x < len(pixels[y]):
        pixels[y][x] = color


def draw_circle(pixels: list[list[tuple[int, int, int, int]]], cx: float, cy: float, r: float, color: tuple[int, int, int, int]) -> None:
    size = len(pixels)
    for y in range(max(0, int(cy - r - 2)), min(size, int(cy + r + 3))):
        for x in range(max(0, int(cx - r - 2)), min(size, int(cx + r + 3))):
            dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if dist <= r:
                put_px(pixels, x, y, color)


def draw_line(pixels: list[list[tuple[int, int, int, int]]], points: list[tuple[float, float]], width: float, color: tuple[int, int, int, int]) -> None:
    for a, b in zip(points, points[1:]):
        ax, ay = a
        bx, by = b
        steps = max(1, int(math.hypot(bx - ax, by - ay) * 1.8))
        for i in range(steps + 1):
            t = i / steps
            x = ax + (bx - ax) * t
            y = ay + (by - ay) * t
            draw_circle(pixels, x, y, width / 2, color)


def draw_rect_round(pixels: list[list[tuple[int, int, int, int]]], radius_ratio: float = 0.23) -> None:
    size = len(pixels)
    radius = size * radius_ratio
    c1 = (17, 24, 27)
    c2 = (13, 17, 19)
    for y in range(size):
        for x in range(size):
            dx = max(radius - x - 0.5, 0, x + 0.5 - (size - radius))
            dy = max(radius - y - 0.5, 0, y + 0.5 - (size - radius))
            if math.hypot(dx, dy) <= radius:
                t = (x + y) / (2 * size)
                r, g, b = blend(c1, c2, t)
                pixels[y][x] = (r, g, b, 255)


def draw_cloud(pixels: list[list[tuple[int, int, int, int]]], scale: float) -> None:
    white = (248, 250, 252, 255)
    draw_circle(pixels, 185 * scale, 258 * scale, 65 * scale, white)
    draw_circle(pixels, 250 * scale, 214 * scale, 82 * scale, white)
    draw_circle(pixels, 327 * scale, 263 * scale, 68 * scale, white)
    draw_line(pixels, [(152 * scale, 308 * scale), (346 * scale, 308 * scale)], 78 * scale, white)
    bolt = (22, 163, 184, 255)
    poly = [
        (248, 180), (206, 277), (261, 277), (242, 348),
        (314, 245), (256, 245), (277, 180)
    ]
    fill_polygon(pixels, [(x * scale, y * scale) for x, y in poly], bolt)


def fill_polygon(pixels: list[list[tuple[int, int, int, int]]], poly: list[tuple[float, float]], color: tuple[int, int, int, int]) -> None:
    ys = [p[1] for p in poly]
    for y in range(max(0, int(min(ys))), min(len(pixels), int(max(ys)) + 1)):
        nodes: list[float] = []
        j = len(poly) - 1
        for i in range(len(poly)):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if (yi < y <= yj) or (yj < y <= yi):
                nodes.append(xi + (y - yi) / (yj - yi) * (xj - xi))
            j = i
        nodes.sort()
        for i in range(0, len(nodes), 2):
            if i + 1 >= len(nodes):
                break
            for x in range(max(0, int(nodes[i])), min(len(pixels), int(nodes[i + 1]) + 1)):
                put_px(pixels, x, y, color)


def png_bytes(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in row) for row in pixels)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def make_icon(size: int) -> bytes:
    pixels = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]
    scale = size / 512
    draw_rect_round(pixels)
    draw_line(pixels, [(124 * scale, 334 * scale), (205 * scale, 354 * scale), (262 * scale, 315 * scale), (390 * scale, 286 * scale)], 32 * scale, (22, 163, 184, 255))
    draw_circle(pixels, 126 * scale, 334 * scale, 24 * scale, (250, 204, 21, 255))
    draw_circle(pixels, 389 * scale, 286 * scale, 24 * scale, (34, 197, 94, 255))
    draw_cloud(pixels, scale)
    draw_circle(pixels, 374 * scale, 144 * scale, 40 * scale, (248, 250, 252, 255))
    draw_circle(pixels, 374 * scale, 144 * scale, 24 * scale, (17, 24, 27, 255))
    draw_line(pixels, [(374 * scale, 118 * scale), (374 * scale, 170 * scale)], 13 * scale, (248, 250, 252, 255))
    draw_line(pixels, [(348 * scale, 144 * scale), (400 * scale, 144 * scale)], 13 * scale, (248, 250, 252, 255))
    return png_bytes(pixels)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SHELL_ASSETS.mkdir(parents=True, exist_ok=True)
    sizes = {
        OUT_DIR / "icon-192.png": 192,
        OUT_DIR / "icon-512.png": 512,
        OUT_DIR / "icon-maskable-512.png": 512,
        SHELL_ASSETS / "icon-512.png": 512,
    }
    android_res = ROOT / "android" / "app" / "src" / "main" / "res"
    mipmap_sizes = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for folder, size in mipmap_sizes.items():
        target_dir = android_res / folder
        if target_dir.exists():
            sizes[target_dir / "ic_launcher.png"] = size
            sizes[target_dir / "ic_launcher_round.png"] = size
            sizes[target_dir / "ic_launcher_foreground.png"] = size
    for path, size in sizes.items():
        path.write_bytes(make_icon(size))


if __name__ == "__main__":
    main()
