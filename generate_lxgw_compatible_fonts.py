#!/usr/bin/env python3
"""由未修改的服务器副本生成保留多语言名称的 Word Regular 兼容字体。"""
import os
from pathlib import Path

from fontTools.ttLib import TTFont

from generate_profile import ROOT


FONT_DIR = ROOT / "fonts" / "lxgw-ios"
SOURCE_NAMES = [
    "LXGWWenKaiMonoScreen.ttf",
    "LXGWWenKaiMonoGBScreen.ttf",
    "LXGWWenKaiGBScreen.ttf",
    "LXGWWenKaiScreen.ttf",
    "LXGWNeoZhiSongScreen.ttf",
    "LXGWNeoXiHeiScreenFull.ttf",
    "LXGWNeoZhiSongScreenFull.ttf",
    "LXGWNeoXiHeiScreen.ttf",
]


def with_regular(value: str, separator: str = " ") -> str:
    suffix = f"{separator}Regular"
    return value if value.endswith(suffix) else f"{value}{suffix}"


def make_compatible_font(source: Path, destination: Path) -> None:
    font = TTFont(source)
    names = font["name"]

    # 仿照上游已有的 LXGWWenKai-Regular：Family、Subfamily、Unique ID、
    # Full Name 维持原样，仅给具体字形的 PostScript Name 添加 -Regular。
    # Core Text 优先用 PostScript Name 创建字体，WordprocessingML 则继续按
    # 原 primary family name 匹配文档中的字体引用。
    for record in names.names:
        if record.nameID == 6:
            record.string = with_regular(
                record.toUnicode(), separator="-"
            ).encode(record.getEncoding())

    temp = destination.with_suffix(".tmp.ttf")
    font.save(temp, reorderTables=False)
    font.close()
    os.replace(temp, destination)


def main() -> None:
    for source_name in SOURCE_NAMES:
        source = FONT_DIR / source_name
        if not source.is_file():
            raise SystemExit(f"未修改的服务器字体副本不存在：{source.name}")
        destination = source.with_name(f"{source.stem}-Regular.ttf")
        make_compatible_font(source, destination)
        print(f"{source.name} -> {destination.name}")


if __name__ == "__main__":
    main()
