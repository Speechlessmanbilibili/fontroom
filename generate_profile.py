#!/usr/bin/env python3
"""生成 iOS 字体描述文件（.mobileconfig）。

用法：
    python generate_profile.py                         # 默认：六个最新静态家族
    python generate_profile.py --fonts <目录或ttf文件>...   # 任意字体来源
    python generate_profile.py --out <输出目录>

字体来源目录可用环境变量覆盖：
    HANLINK_FONT_DIR、HANLINK_INTERROBANG_FONT_DIR、CJK_PUNCT_FONT_DIR、
    CJK_PUNCT_INTERROBANG_FONT_DIR、INTERROBANG_BRIDGE_FONT_DIR、
    TH_GROTESK_FONT_DIR
"""
import argparse
import os
import plistlib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get("IOS_FONT_PROFILE_OUT", ROOT / "profiles"))
DEFAULT_FONT_DIRS = [
    Path(os.environ.get(
        "HANLINK_FONT_DIR",
        ROOT.parent / "Hanlink-Sans" / "fonts" / "static",
    )),
    Path(os.environ.get(
        "HANLINK_INTERROBANG_FONT_DIR",
        ROOT.parent / "Hanlink-Interrobang" / "fonts-interrobang" / "static",
    )),
    Path(os.environ.get(
        "CJK_PUNCT_FONT_DIR",
        ROOT.parent / "CJK-Punct-Bridge" / "fonts" / "static",
    )),
    Path(os.environ.get(
        "CJK_PUNCT_INTERROBANG_FONT_DIR",
        ROOT.parent / "CJK-Punct-Bridge" / "fonts-interrobang" / "static",
    )),
    Path(os.environ.get(
        "INTERROBANG_BRIDGE_FONT_DIR",
        ROOT.parent / "CJK-Punct-Bridge" / "fonts-interrobang-bridge" / "static",
    )),
    Path(os.environ.get(
        "TH_GROTESK_FONT_DIR",
        ROOT.parent / "ThGrotesk" / "fonts" / "static",
    )),
]
PROFILE_ID = "org.silentperson.hanlink-sans-cjkpunct"




def display_name(path: Path) -> str:
    name = path.stem
    if name.startswith("HanlinkSansInterrobang"):
        family, style = "Hanlink Sans ?!", name[len("HanlinkSansInterrobang-"):]
    elif name.startswith("CJKPunctBridgeInterrobang"):
        family, style = "CJK Punct Bridge ?!", name[len("CJKPunctBridgeInterrobang-"):]
    elif name.startswith("HanlinkSans"):
        family, style = "Hanlink Sans", name[len("HanlinkSans-"):]
    elif name.startswith("CJKPunctBridge"):
        family, style = "CJK Punct Bridge", name[len("CJKPunctBridge-"):]
    elif name.startswith("InterrobangBridge"):
        family, style = "Interrobang Bridge", name[len("InterrobangBridge-"):]
    elif name.startswith("ThGrotesk"):
        family, style = "Th Grotesk", name[len("ThGrotesk-"):]
    else:
        family, style = "Custom Font", name
    return f"{family} {style}".replace("  ", " ")


def discover_fonts(dirs=None) -> list:
    """扫描字体目录，返回 [{path, name, size}]，按文件名排序。"""
    dirs = dirs if dirs is not None else DEFAULT_FONT_DIRS
    by_name = {}
    for d in dirs:
        d = Path(d)
        if d.is_dir():
            candidates = sorted(d.glob("*.ttf"))
        elif d.is_file() and d.suffix == ".ttf":
            candidates = [d]
        else:
            candidates = []
        for path in candidates:
            # PayloadIdentifier is derived from the filename stem, so duplicate
            # filenames must resolve to one source. Later, dedicated directories
            # intentionally override earlier compatibility/build directories.
            by_name[path.name] = path
    if not by_name:
        raise SystemExit(f"未找到字体：{dirs}")
    return sorted(by_name.values(), key=lambda p: p.name)


def make_profile(
    name: str,
    fonts: list,
    description: str,
    profile_id: str = PROFILE_ID,
) -> bytes:
    """构建一个描述文件的二进制 plist 字节。Font 必须传原始字体字节！"""
    payloads = []
    for path in fonts:
        payloads.append({
            "PayloadType": "com.apple.font",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"{profile_id}.font.{path.stem}",
            "PayloadUUID": str(uuid.uuid4()),
            "PayloadDisplayName": display_name(path),
            # Name 是 com.apple.font 的必需键（字体文件名），缺失会被 iOS
            # 判定「包含无效字体」（参考 Apple 文档示例与 keyman 实测 profile）。
            "Name": path.name,
            "PayloadDescription": "Configures Font settings",
            # 必须传原始字体字节！plistlib 序列化时会自行 base64 编码；
            # 若先 b64encode 一次再传入，会形成双重 base64，iOS 解码后
            # 拿到的是 base64 文本而非字体数据，直接报「包含无效字体」。
            "Font": path.read_bytes(),
        })
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"{profile_id}.{name}",
        "PayloadUUID": str(uuid.uuid4()),
        "PayloadDisplayName": description,
        "PayloadDescription": description,
        "PayloadOrganization": "SilentPerson",
        "PayloadRemovalDisallowed": False,
        "PayloadContent": payloads,
    }
    # 二进制 plist：Apple Configurator 生成的描述文件即为二进制格式，
    # data 存原始字节（无 base64/缩进问题），iOS 解析最稳。
    return plistlib.dumps(profile, fmt=plistlib.FMT_BINARY)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="生成 iOS 字体描述文件",
        epilog="示例：\n"
               "  python generate_profile.py                                   # 默认：六个最新静态家族\n"
               "  python generate_profile.py --fonts C:/fonts /x/My.ttf        # 指定目录或文件\n"
               "  python generate_profile.py --filter Italic                   # 只要斜体\n"
               "  python generate_profile.py --filter Regular --filter Bold    # 多个过滤（OR）\n"
               "  python generate_profile.py --name \"我的字体\" --out build/out   # 自定义名与输出目录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--fonts", nargs="+", help="字体目录或 .ttf 文件（默认六个静态字体目录）")
    ap.add_argument("--filter", action="append", default=[], help="按文件名子串过滤（可多次，OR 关系）")
    ap.add_argument("--name", default=None, help="全量包的显示名（默认“全部 N 个字体”）")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="输出目录")
    ap.add_argument("--pairs", action="store_true", help="额外生成同字重的正体 + 斜体配对包")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("*.mobileconfig"):
        p.unlink()

    if args.fonts:
        font_dirs = [Path(x) for x in args.fonts]
    else:
        font_dirs = None
    fonts = discover_fonts(font_dirs)
    if args.filter:
        kept = [p for p in fonts if any(f in p.name for f in args.filter)]
        dropped = len(fonts) - len(kept)
        fonts = kept
        print(f"过滤 {args.filter}: 保留 {len(fonts)}，排除 {dropped}")
    if not fonts:
        raise SystemExit("过滤后没有字体")
    print(f"发现 {len(fonts)} 个字体")

    # 全量包：每个家族独立一个描述文件，更新一个不用重装另一个。
    # 前缀按长短排序匹配（Interrobang 文件名以标准前缀开头，必须先匹配）。
    PACK_GROUPS = [
        ("HanlinkSansInterrobang", "HanlinkSansInterrobang-", "Hanlink Sans ?!"),
        ("CJKPunctBridgeInterrobang", "CJKPunctBridgeInterrobang-", "CJK Punct Bridge ?!"),
        ("HanlinkSans", "HanlinkSans-", "Hanlink Sans"),
        ("CJKPunctBridge", "CJKPunctBridge-", "CJK Punct Bridge"),
        ("InterrobangBridge", "InterrobangBridge-", "Interrobang Bridge"),
        ("ThGrotesk", "ThGrotesk-", "Th Grotesk"),
    ]
    for key, prefix, label in PACK_GROUPS:
        members = [p for p in fonts if p.name.startswith(prefix)]
        if not members:
            continue
        data = make_profile(key, members, f"{label} 全部 {len(members)} 个字体")
        (out_dir / f"{key}.mobileconfig").write_bytes(data)
        print(f"  {key}.mobileconfig  {len(data)/1024/1024:.1f} MB")

    # 两两配对：同字重的正体 + 斜体（按文件前缀分组）
    if args.pairs:
        by_weight = {}
        for p in fonts:
            prefix = p.stem.split("-", 1)[0]          # HanlinkSans / CJKPunctBridge
            style = p.stem.split("-", 1)[1] if "-" in p.stem else p.stem
            italic = "Italic" in style or style == "Italic"
            weight = style.replace("Italic", "") or "Regular"
            by_weight.setdefault((prefix, weight), []).append(p)
        for (prefix, weight), pair in sorted(by_weight.items()):
            if len(pair) < 2:
                continue
            desc = " + ".join(display_name(p) for p in pair)
            data = make_profile(f"Pair-{prefix}-{weight}", pair, desc)
            (out_dir / f"{prefix}-{weight}.mobileconfig").write_bytes(data)
            print(f"  {prefix}-{weight}.mobileconfig  {len(data)/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
