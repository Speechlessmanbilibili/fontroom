#!/usr/bin/env python3
"""生成 iOS 字体描述文件（.mobileconfig）。

用法：
    python -X utf8 generate_profile.py
    python -X utf8 generate_profile.py --fonts <字体目录或文件> --out <输出目录>
    python -X utf8 generate_profile.py --pairs

默认读取相邻字体工程的静态输出目录，配置入口见 docs/usage.md。
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


# 方正字库：文件名是内部代号，需要映射成可读的中文名。
FOUNDER_FONT_NAMES = {
    "FZNBSJW": "方正新报宋简体",
    "FZQingKBYSJF-B": "方正清刻本悦宋 简繁 B",
    "FZQingKBYSJF-EL": "方正清刻本悦宋 简繁 EL",
    "FZQingKBYSJF-L": "方正清刻本悦宋 简繁 L",
    "FZQingKBYSJF-M": "方正清刻本悦宋 简繁 M",
    "FZQingKBYSJF-R": "方正清刻本悦宋 简繁 R",
    "FZQingKBYSJW-B": "方正清刻本悦宋 简 B",
    "FZQingKBYSJW-EL": "方正清刻本悦宋 简 EL",
    "FZQingKBYSJW-L": "方正清刻本悦宋 简 L",
    "FZQingKBYSJW-M": "方正清刻本悦宋 简 M",
    "FZQingKBYSJW-R": "方正清刻本悦宋 简 R",
    "FZXSSB": "方正新書宋",
    "FZXSSJW": "方正新书宋简体",
    "FZXSSK": "方正新书宋_GBK",
    "FZZHJW": "方正正黑简体",
    "FZZHK": "方正正黑_GBK",
}


def _font_family(path: Path) -> str:
    """读字体自带的 family 名（nameID 1）。读不到就返回空串。"""
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(str(path), lazy=True)
        fam = ""
        for rec in f["name"].names:
            if rec.nameID == 1 and rec.platformID == 3 and rec.langID == 0x409:
                fam = rec.toUnicode()
                break
        f.close()
        return fam
    except Exception:
        return ""


# 思源宋体：文件名形如 SourceHanSerifSC-Medium.otf，
# 前缀区分语言版本，中缀是字重。顺序敏感，长的要排前面。
SOURCE_HAN_PREFIXES = [
    ("SourceHanSerifSC", "简"),
    ("SourceHanSerifTC", "繁"),
    ("SourceHanSerifHC", "港"),
    ("SourceHanSerifK", "韩"),
    ("SourceHanSerif", "日"),
]


def _source_han_name(stem: str):
    """解析思源宋体与思源黑体的文件名，返回地区和变体显示名。"""
    if stem.startswith("SourceHanSans") and "-" in stem:
        region, style = stem[len("SourceHanSans"):].split("-", 1)
        variant = ""
        if region.startswith("HW"):
            region, variant = region[2:], " HW"
        labels = {"SC": "简", "TC": "繁", "HC": "港", "K": "韩", "": "日",
                  "CN": "简", "TW": "繁", "HK": "港", "KR": "韩", "JP": "日"}
        if region in labels:
            if region in {"CN", "TW", "HK", "KR", "JP"}:
                variant += " 地区子集"
            return f"思源黑体{labels[region]}{variant} {style}"
    for prefix, lang in SOURCE_HAN_PREFIXES:
        if stem.startswith(prefix + "-"):
            style = stem[len(prefix) + 1:]
            return "思源宋体%s %s" % (lang, style)
    return None


# Source Serif 4：文件名形如 SourceSerif4-Caption-BlackItalic.ttf，
# 第一段是光学尺寸档位，第二段是字重。档位顺序敏感，长的排前面。
SOURCE_SERIF_OPTICAL = {
    "Text": "Text",
    "Caption": "Caption",
    "SmText": "SmText",
    "Subhead": "Subhead",
    "Display": "Display",
}
SOURCE_SERIF_STYLES = (
    ("BoldItalic", "Bold Italic"),
    ("ExtraLightItalic", "ExtraLight Italic"),
    ("SemiboldItalic", "Semibold Italic"),
    ("LightItalic", "Light Italic"),
    ("BlackItalic", "Black Italic"),
    ("Regular", "Regular"),
    ("Italic", "Italic"),
    ("Bold", "Bold"),
    ("ExtraLight", "ExtraLight"),
    ("Semibold", "Semibold"),
    ("Light", "Light"),
    ("Black", "Black"),
)


def _source_serif_name(stem: str):
    """解析 Source Serif 4 的文件名，返回显示名；不是它则返回 None。

    命名沿用官方规则：默认档是 SourceSerif4-Regular.ttf，其余档位带档位名，
    例如 SourceSerif4Caption-BoldItalic.ttf。
    """
    if not stem.startswith("SourceSerif4"):
        return None
    rest = stem[len("SourceSerif4"):]
    opt = ""
    for cand in ("Caption", "SmText", "Subhead", "Display"):
        if rest.startswith(cand + "-"):
            opt = cand
            rest = rest[len(cand):]
            break
    if not rest.startswith("-"):
        return None
    style = rest[1:]
    for key, label in SOURCE_SERIF_STYLES:
        if style == key:
            prefix = ("Source Serif 4 " + opt) if opt else "Source Serif 4"
            return "%s %s" % (prefix, label)
    return None


def display_name(path: Path) -> str:
    name = path.stem
    han = _source_han_name(name)
    if han:
        return han
    serif = _source_serif_name(name)
    if serif:
        return serif
    if name.startswith("SourceSans3-"):
        style = name[len("SourceSans3-"):]
        if style.endswith("It"):
            style = style[:-2] + " Italic"
        else:
            style = style.replace("Italic", " Italic")
        return "Source Sans 3 " + style.strip()
    if name.startswith("Charis-"):
        return "Charis " + name[len("Charis-"):].replace("Italic", " Italic").strip()
    if name in FOUNDER_FONT_NAMES:
        return FOUNDER_FONT_NAMES[name]
    for stem, display in FOUNDER_FONT_NAMES.items():
        if stem.lower() == name.lower():
            return display
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
    """扫描独立 TTF/OTF 文件，按文件名排序；后列来源覆盖同名文件。"""
    dirs = dirs if dirs is not None else DEFAULT_FONT_DIRS
    by_name = {}
    for d in dirs:
        d = Path(d)
        if d.is_dir():
            candidates = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".ttf", ".otf"))
        elif d.is_file() and d.suffix.lower() in (".ttf", ".otf"):
            candidates = [d]
        else:
            candidates = []
        for path in candidates:
            # 描述文件以文件名生成标识；专用来源优先于前面的兼容目录。
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
            # Name 是安装前显示的名称，系统安装后使用字体的内部名称。
            "Name": path.name,
            "PayloadDescription": "Configures Font settings",
            # Font 保存原始字体字节，由 plistlib 完成序列化。
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
        description="字房 / Fontroom：生成 iOS 字体描述文件",
        epilog="示例：\n"
               "  python -X utf8 generate_profile.py                                   # 默认：六个静态家族\n"
               "  python -X utf8 generate_profile.py --fonts C:/fonts C:/My.otf         # 指定目录或文件\n"
               "  python -X utf8 generate_profile.py --filter Italic                    # 筛选斜体\n"
               "  python -X utf8 generate_profile.py --filter Regular --filter Bold     # 多个过滤按或匹配\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--fonts", nargs="+", help="字体目录或独立 .ttf/.otf 文件（默认六个静态字体目录）")
    ap.add_argument("--filter", action="append", default=[], help="按文件名子串过滤（可多次，OR 关系）")
    ap.add_argument("--name", default=None, help=argparse.SUPPRESS)
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
