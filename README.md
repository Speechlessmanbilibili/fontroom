# iOS 字体安装服务器

在 iOS 上安装中文字体，常见的做法是借助字体管理类应用。这类应用一般需要电脑端与手机端配合，由电脑提供字体、手机负责接收。实际使用中容易遇到这样几种情况：

- **开启本地服务、弹出提示的那一刻即闪退**，字体来不及下发；
- **字体体积较大时，弹出提示的瞬间就直接闪退**，体积越大越明显；
- **需要装入多款字体时只能逐个添加**，重复操作繁琐；
- **具体装入哪几款依赖应用内手工勾选**，筛选成本高。

本项目针对的正是这几处：不依赖任何应用，改用 iOS 原生的配置描述文件（`.mobileconfig`）承载字体，由系统字体库直接注册。描述文件由电脑经局域网下发，手机侧仅需下载并确认安装。字体一经装入即属于系统，与任何应用无关，也不存在需要启动或维持的本地服务。

技术上有三点值得说明：

- **字体数据以二进制形式内嵌在描述文件之中**，不存在远程字体地址，安装与运行均不依赖外部服务。
- **单个文件可以承载整个字体族**。默认配置为每个家族 9 个正体与 9 个斜体，共 18 个静态 TTF；实测上百兆的单包同样可以一次安装完成（见排障附录第 5 节）。
- **全部流程不出局域网**。从生成、下载到安装，数据不经过任何外部服务器。

## 快速开始

```bash
pip install fonttools

# 1. 生成描述文件（默认扫描相邻字体仓库的六个静态目录）
python generate_profile.py

# 2. 启动局域网服务器
python server.py
```

手机 Safari 打开控制台输出的局域网地址，点击页面顶部对应的家族按钮下载描述文件，随后在「设置 → 已下载描述文件 → 安装」，再到「设置 → 通用 → 字体」确认启用。

> **端口说明**：Windows 启用 Hyper-V 或 WSL 之后会保留大段 TCP 端口（实测 8000-8199、8201-8300、8561-9461 等区间均被占用），落在保留区间内的端口绑定时会抛出 `WinError 10013`。`server.py` 因此在 8765 失败后依次尝试 8788、9000、9700、12345，并打印实际使用的端口。如需固定端口，设置环境变量即可：
>
> ```bash
> FONT_SERVER_PORT=9700 python server.py
> ```

## 命令行选择字体

字体不必逐个手工挑选，`generate_profile.py` 支持按目录、按文件名子串、按字重批量指定：

```bash
python generate_profile.py                                        # 默认：全部字体
python generate_profile.py --fonts C:/fonts /x/MyFont.ttf        # 指定目录或单个 ttf 文件
python generate_profile.py --filter Italic                       # 只要斜体（按文件名子串，可多次 OR）
python generate_profile.py --filter Regular --filter Bold        # 只要 Regular 和 Bold
python generate_profile.py --name "我的字体" --out build/out      # 自定义包名与输出目录
python generate_profile.py --pairs                               # 额外生成同字重正体 + 斜体配对包
```

六个字体来源目录可用环境变量覆盖：`HANLINK_FONT_DIR`、`HANLINK_INTERROBANG_FONT_DIR`、`CJK_PUNCT_FONT_DIR`、`CJK_PUNCT_INTERROBANG_FONT_DIR`、`INTERROBANG_BRIDGE_FONT_DIR`、`TH_GROTESK_FONT_DIR`。默认读取相邻仓库的静态输出目录——**字体二进制不会复制或提交到本仓库**，仓库只承载实现。

> `TH_GROTESK_FONT_DIR` 默认指向 `../ThGrotesk/fonts/static`。iOS 的 `com.apple.font` 只接受静态字体，因此 Th Grotesk 需要先自行将变量字体实例化为静态 TTF 再放入该目录。

## 服务器接口

| 接口 | 说明 |
| --- | --- |
| `GET /` | 安装页：全量包、预生成分组包、自定义勾选 |
| `GET /profiles/…` | 预生成的描述文件（`application/x-apple-aspen-config`） |
| `GET /fonts.json` | 可用字体列表（勾选 UI 用） |
| `GET /profiles.json` | 预生成描述文件列表 |
| `POST /api/profile` | 按勾选字体动态生成：`{"fonts":["A.ttf","B.ttf"],"name":"…"}` → 返回 `.mobileconfig` |

前端页面针对移动端 Safari 的触摸与展示做了优化，分为三个区域：独立字体家族卡片、预生成合集包列表，以及带快捷筛选的自选字体面板。需要自行组合字体时，可用快捷芯片按家族、按正斜体一键筛选，不必逐条勾选。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `generate_profile.py` | 描述文件生成器：全量包 + 字重配对包，支持 `--fonts/--filter/--name` |
| `generate_lxgw_profiles.py` | 落霞孤鹜合集与 Word 兼容版描述文件生成器 |
| `server.py` | 局域网服务器：静态描述文件托管 + 动态生成 API |
| `index.html` | 安装页：全量下载、分组包列表、自定义勾选 |
| 外部字体目录 | 默认读取相邻字体仓库，本仓库存放实现而非字体 |

字体来源：[Hanlink Sans](https://github.com/Speechlessmanbilibili/Hanlink-Sans)、[Hanlink ?!](https://github.com/Speechlessmanbilibili/Hanlink-Interrobang)、[CJK Punct Bridge](https://github.com/Speechlessmanbilibili/CJK-Punct-Bridge)、[Th Grotesk](https://github.com/Speechlessmanbilibili/ThGrotesk)。

---

## 排障附录：iOS 报「包含无效字体」

以下记录的是一次完整排障过程。iOS 的 `com.apple.font` payload 只支持 **base64 内嵌字体**（不存在远程 URL 键），而当系统报「包含无效字体」时，原因通常不在字体本身，而在描述文件的生成方式。以下按可能性从高到低排列。

### 1. 双重 base64 编码

`Font` 键**必须传原始字体字节**，由 plistlib 序列化时自行完成 base64 编码：

```python
"Font": path.read_bytes(),                      # 正确
"Font": base64.b64encode(path.read_bytes()),    # 错误：双重编码
```

若先 `b64encode` 一次再交给 plistlib，XML 输出时会被再编码一次。iOS 解码后得到的是 base64 文本而非字体数据，CoreText 加载失败，随即报「包含无效字体」。二进制 plist 同样会中招（存进去的是 base64 文本字节）。

排查方法是做树级 diff，对比可用 profile 与自有 profile 的 `Font` 值——看开头是 `\x00\x01\x00\x00`（TTF 魔数）还是 `AAEAAAAR...`（base64 文本），一眼可辨。

### 2. `Name` 键缺失

`com.apple.font` payload 有一个**必需键 `Name`**，其值为字体文件名（如 `HanlinkSans-Regular.ttf`）。Apple 文档示例与实测可用的 profile 中均包含该键，缺失时 iOS 会直接判定描述文件无效。注意 `PayloadDisplayName` 不能替代 `Name`。

### 3. 服务器不应压缩 `.mobileconfig`

Safari 下载描述文件并交给系统安装器时可能**不做解压**。若服务器返回 `Content-Encoding: gzip`，安装器拿到的是 gzip 二进制数据，解析随即失败。局域网场景下直接传输原始文件更为可靠——文件大一些，但结果正确。

### 4. Content-Type 必须唯一且正确

必须为 `application/x-apple-aspen-config`。需要注意不能通过 `end_headers()` 追加标头：`SimpleHTTPRequestHandler` 已经发出默认的 `application/octet-stream`，追加会产生两个 `Content-Type` 标头，iOS 可能因此识别错误。正确做法是覆盖 `extensions_map`：

```python
class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mobileconfig": "application/x-apple-aspen-config",
    }
```

### 5. 关于「15–20 MB 描述文件上限」的传言

社区流传 iOS 无法安装大于 15–20 MB 的描述文件，常被引用的例子是 16 MB 的思源宋体安装失败。但本项目 189.7 MB 的全量包（36 个字体）在修复上述问题后**实测一次安装成功**。此前大文件的失败，很可能同样是编码或格式问题，而非体积限制本身。

如果仍有顾虑，可以按字重两两配对生成小包——本项目 `profiles/` 目录下两种形式都保留着。

### 6. 调试方法论：黄金标准对照

找不到头绪时，用一份「确定可用」的 profile 作为黄金标准逐步对照（本项目采用了 [keyman 的字体 profile](https://github.com/keymanapp/r.keymanweb.com)）：

1. **模板替换字体**：把可用 profile 的字体数据替换成自己的——用于隔离「字体因素」，能装则说明字体没有问题；
2. **重新序列化**：用 plistlib 重新 dump 可用 profile 的全部原值——用于隔离「序列化器因素」，能装则说明 plistlib 的输出格式没有问题；
3. **单变量修改**：在可用基底上每次只改一个值（identifier、UUID 大小写、中文文案等）——逐个排除「值因素」；
4. **树级 diff**：递归对比两棵 plist 的所有键值。本项目最终正是靠这一步定位到 `Font` 值的编码差异。

## 许可证

- 本项目的服务器、生成器、页面与文档以 [MIT License](LICENSE) 发布。
- 字体来源仓库中的字体分别受其自身的 [SIL Open Font License 1.1](https://github.com/Speechlessmanbilibili/Hanlink-Sans/blob/main/OFL.txt) 约束；MIT 许可证不适用于字体二进制。
- 排障过程参考了 keyman 公开的字体描述文件结构。
