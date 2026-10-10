#!/usr/bin/env python3
"""从服务器字体副本生成落霞孤鹜合集与 Word Regular 兼容版描述文件。"""
from pathlib import Path

from generate_profile import ROOT, make_profile


FONT_DIR = ROOT / "fonts" / "lxgw-ios"
OUT_DIR = ROOT / "profiles"
EXTRA_FONT_DIR = ROOT / "fonts" / "lxgw-extra"

COLLECTION_FONTS = [
    "LXGWWenKaiMonoScreen-Regular.ttf",
    "LXGWWenKaiMonoGBScreen-Regular.ttf",
    "LXGWWenKaiGBScreen-Regular.ttf",
    "LXGWWenKaiScreen-Regular.ttf",
    "LXGWNeoZhiSongScreen-Regular.ttf",
    "LXGWNeoXiHeiScreenFull-Regular.ttf",
    "LXGWNeoZhiSongScreenFull-Regular.ttf",
    "LXGWNeoXiHeiScreen-Regular.ttf",
    "LXGWWenKai-Regular.ttf",
    "LXGWWenKaiMono-Light.ttf",
    "LXGWWenKaiMono-Medium.ttf",
    "LXGWWenKai-Light.ttf",
    "LXGWWenKai-Medium.ttf",
    "LXGWWenKaiMono-Regular.ttf",
]

WORD_REGULAR_FONTS = [
    "LXGWWenKaiMonoScreen-Regular.ttf",
    "LXGWWenKaiMonoGBScreen-Regular.ttf",
    "LXGWWenKaiGBScreen-Regular.ttf",
    "LXGWWenKaiScreen-Regular.ttf",
    "LXGWNeoZhiSongScreen-Regular.ttf",
    "LXGWNeoXiHeiScreenFull-Regular.ttf",
    "LXGWNeoZhiSongScreenFull-Regular.ttf",
    "LXGWNeoXiHeiScreen-Regular.ttf",
]


def require_fonts(names: list[str], source_dir: Path = FONT_DIR) -> list[Path]:
    fonts = [source_dir / name for name in names]
    missing = [path.name for path in fonts if not path.is_file()]
    if missing:
        raise SystemExit(f"服务器字体副本不存在：{', '.join(missing)}")
    return fonts


def write_profile(
    filename: str,
    name: str,
    font_names: list[str],
    description: str,
    profile_id: str,
    source_dir: Path = FONT_DIR,
) -> None:
    data = make_profile(
        name,
        require_fonts(font_names, source_dir),
        description,
        profile_id=profile_id,
    )
    path = OUT_DIR / filename
    temporary = path.with_suffix(".tmp.mobileconfig")
    temporary.write_bytes(data)
    temporary.replace(path)
    print(f"{path.name}  {len(font_names)}款  {len(data) / 1024 / 1024:.1f} MB")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    extra = [EXTRA_FONT_DIR / name for name in (
        "LXGWNeoXiHeiPlus.ttf", "LXGWNeoXiHei.ttf",
        "LXGWNeoZhiSongPlus.ttf", "LXGWNeoZhiSong.ttf",
    )]
    if all(path.is_file() for path in extra):
        write_profile(
            "霞鹜新晰黑、霞鹜新致宋.mobileconfig",
            "lxgw-xihei-zhisong-extra",
            [path.name for path in extra],
            "霞鹜新晰黑、霞鹜新致宋",
            "org.silentperson.lxgw-xihei-zhisong-extra",
            source_dir=EXTRA_FONT_DIR,
        )
    write_profile(
        "落霞孤鹜字体合集（14款）.mobileconfig",
        "collection14-original-v2",
        COLLECTION_FONTS,
        "落霞孤鹜字体合集（14款）",
        "org.silentperson.lxgw-original-v2",
    )
    write_profile(
        "落霞孤鹜字体合集（Word Regular兼容版，8款）.mobileconfig",
        "collection8-word-regular",
        WORD_REGULAR_FONTS,
        "落霞孤鹜字体合集（Word Regular兼容版8款）",
        "org.silentperson.lxgw-word-regular",
    )


if __name__ == "__main__":
    main()
