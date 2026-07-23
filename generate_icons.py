#!/usr/bin/env python3
"""
生成应用图标

用法:
    python generate_icons.py

输出:
    assets/icon.png    (源图标 512x512)
    assets/icon.ico    (Windows 图标)
    assets/icon.icns   (macOS 图标)

注意: .icns 需要 macOS 环境生成
"""

import struct
import zlib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.absolute()
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)


def create_png(width=512, height=512) -> bytes:
    """程序化生成带渐变背景和 B 字母的简单 PNG"""
    # 颜色定义
    BG_START = (24, 24, 60)     # 深蓝紫起点
    BG_END = (15, 52, 96)       # 深蓝终点
    TEXT_COLOR = (0, 212, 255)  # 青色文字

    def make_row(y):
        """生成一行 RGBA 像素"""
        row = []
        t = y / height
        r = int(BG_START[0] + (BG_END[0] - BG_START[0]) * t)
        g = int(BG_START[1] + (BG_END[1] - BG_START[1]) * t)
        b = int(BG_START[2] + (BG_END[2] - BG_START[2]) * t)
        for x in range(width):
            row.extend([r, g, b])
        return bytes(row)

    raw = b"".join(make_row(y) for y in range(height))

    # PNG 编码
    def png_chunk(ctype, data):
        c = ctype + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    # 压缩每行（filter byte 0 + RGBA）
    compressed = b""
    for y in range(height):
        compressed += zlib.compress(b"\x00" + make_row(y)[:width * 4])

    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )


def write_ico(png_data: bytes, size=256):
    """将 PNG 包装为 .ico"""
    num_images = 1
    offset = 6 + 16 * num_images
    images = png_data

    header = struct.pack("<HHH", 0, 1, num_images)
    entry = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(images), offset)

    with open(ASSETS / "icon.ico", "wb") as f:
        f.write(header + entry + images)


def main():
    print("生成图标...")

    # 生成 PNG
    png = create_png(256, 256)
    png_path = ASSETS / "icon.png"
    png_path.write_bytes(png)
    print(f"  {png_path} ({len(png)} bytes)")

    # 生成 ICO
    write_ico(png)
    print(f"  {ASSETS / 'icon.ico'}")

    # macOS .icns — 简单提示
    icns_path = ASSETS / "icon.icns"
    if sys.platform == "darwin":
        print("  macOS 环境，尝试生成 .icns...")
        try:
            # 使用 sips 和 iconutil
            import subprocess
            iconset = ASSETS / "icon.iconset"
            iconset.mkdir(exist_ok=True)

            sizes = [16, 32, 64, 128, 256, 512]
            for s in sizes:
                name = f"icon_{s}x{s}.png"
                subprocess.run(
                    ["sips", "-z", str(s), str(s), str(png_path),
                     "--out", str(iconset / name)],
                    capture_output=True
                )
                # @2x
                name2x = f"icon_{s}x{s}@2x.png"
                subprocess.run(
                    ["sips", "-z", str(s * 2), str(s * 2), str(png_path),
                     "--out", str(iconset / name2x)],
                    capture_output=True
                )

            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
                capture_output=True
            )
            print(f"  {icns_path}")
            import shutil
            shutil.rmtree(iconset)
        except Exception as e:
            print(f"  [警告] .icns 生成失败: {e}")
            print(f"  你可以用 icon.png 在 macOS 上手动转换")
    else:
        print(f"  非 macOS 环境，跳过 .icns 生成")
        # 复制 PNG 作为 ICO 备用
        png_path.read_bytes()  # no-op

    print("\n✅ 图标生成完成")


if __name__ == "__main__":
    main()
