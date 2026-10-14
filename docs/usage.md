# 使用与维护

## 自备字体

设置 `FONT_DIR` 后启动服务，网页中的“自选字体”会读取该目录的独立 TTF/OTF 文件：

```powershell
$env:FONT_DIR = "D:\Fonts"
python -X utf8 server.py
```

目录内的文件按名称排序；多个来源存在同名文件时，后列来源优先。独立字体集合的拆分在接入前完成，网页字体使用相应的桌面版文件。

## 来源目录

| 配置项 | 默认来源 |
|---|---|
| `HANLINK_FONT_DIR` | `../Hanlink-Sans/fonts/static` |
| `HANLINK_INTERROBANG_FONT_DIR` | `../Hanlink-Interrobang/fonts-interrobang/static` |
| `CJK_PUNCT_FONT_DIR` | `../CJK-Punct-Bridge/fonts/static` |
| `CJK_PUNCT_INTERROBANG_FONT_DIR` | `../CJK-Punct-Bridge/fonts-interrobang/static` |
| `INTERROBANG_BRIDGE_FONT_DIR` | `../CJK-Punct-Bridge/fonts-interrobang-bridge/static` |
| `TH_GROTESK_FONT_DIR` | `../ThGrotesk/fonts/static` |
| `CRIMSON_PRO_FONT_DIR` | `fonts/CrimsonPro` |
| `SOURCE_SERIF_FONT_DIR` | `fonts/SourceSerif4` |
| `SOURCE_HAN_SERIF_FONT_DIR` | `fonts/SourceHanSerif` |
| `CHARIS_FONT_DIR` | `fonts/Charis` |
| `FOUNDER_FONT_DIR` | `fonts/founder`，也识别其中的 `Font/` 子目录 |
| `FONT_DIR` | 自备字体目录，按需设置 |

相对路径以仓库为起点。字体与描述文件均在本地保存。

## 基础家族生成器

`generate_profile.py` 按预设文件名前缀生成六类基础家族的描述文件。可选目录、文件、文件名筛选和输出位置：

```powershell
python -X utf8 generate_profile.py --fonts D:\Fonts\Hanlink
python -X utf8 generate_profile.py --filter Regular --filter Bold
python -X utf8 generate_profile.py --pairs
python -X utf8 generate_profile.py --out build/base-profiles
```

多个 `--filter` 按“或”匹配文件名；`--pairs` 额外生成同字重正体与斜体配对文件。任意家族的自由组合可通过网页自选功能完成。

基础生成器会先清理目标目录已有的 `.mobileconfig` 文件，再生成本次结果。独立输出可使用 `--out`；安装网页读取 `profiles/` 顶层的描述文件。

## 落霞孤鹜生成工具

仓库保留原有的落霞孤鹜字体合集与兼容字体处理工具：

```powershell
python -X utf8 generate_lxgw_profiles.py
```

源文件位置与兼容字体处理见 `generate_lxgw_profiles.py` 和 `generate_lxgw_compatible_fonts.py`。各字体继续遵循自身授权条款。

## 服务端口

默认依次尝试 `8765`、`8788`、`9000`、`9700`、`12345`，以终端打印的实际地址为准。固定端口：

```powershell
$env:FONT_SERVER_PORT = "9700"
python -X utf8 server.py
```

## 接口

| 接口 | 返回内容 |
|---|---|
| `GET /` | 安装页面 |
| `GET /fonts.json` | 字体名称、显示名称与文件体积 |
| `GET /profiles.json` | 已生成的描述文件列表 |
| `GET /status.json` | 页面和描述文件的最新修改时间 |
| `GET /profiles/文件名.mobileconfig` | 安装描述文件，支持字节范围下载 |
| `POST /api/profile` | 按勾选字体即时生成描述文件 |

动态请求示例：

```json
{"fonts":["Example-Regular.ttf","Example-Bold.otf"],"name":"常用字体"}
```

安装文件以 `application/x-apple-aspen-config` 返回。

## 仓库与页面

两个仓库同步通用字体扫描、描述文件封装与服务能力。页面卡片和本地字体资产分别维护，按各自的安装入口配置展示。公开版本保留原有生成工具和六个家族入口；私有版本维护个人常用字体库与新增家族专用生成器。

调整通用格式支持时检查两侧核心代码；专用生成器与字体卡片按对应仓库的用途维护。
