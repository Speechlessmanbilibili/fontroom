# iOS 字体安装服务器

通过 iOS 配置描述文件（`.mobileconfig`）在局域网内给 iPhone/iPad 安装字体。
默认从相邻的 Hanlink Sans、Hanlink Interrobang、CJK Punct Bridge、
Interrobang Bridge 与 ThGrotesk 工作区读取最新静态字体，生成六个彼此独立
的描述文件：Hanlink/CJK Punct 的标准版与 `?!` 版各一个，独立的西文
Interrobang Bridge 一个，Th Grotesk 一个；每个文件内含 9 个正体和 9 个斜体。
字体文件与生成的 `profiles/` 仅在本机使用，不提交到本仓库。

## 快速开始

```bash
pip install fonttools

# 1. 生成六个家族描述文件（默认扫描四个字体仓库的六个静态目录）
python generate_profile.py

# 2. 启动局域网服务器（默认 0.0.0.0:8765）
python server.py
```

> 端口说明：Windows 开启 Hyper-V 或 WSL 后会保留大段 TCP 端口
> （实测 8000-8199、8201-8300、8561-9461 等区间都被占），落在保留区间内的
> 端口绑定时会报 `WinError 10013`。`server.py` 因此在 8765 失败时会依次尝试
> 8788、9000、9700、12345，并打印实际使用的端口。要固定端口就设环境变量：
>
> ```bash
> FONT_SERVER_PORT=9700 python server.py
> ```

手机 Safari 打开 `http://<电脑局域网IP>:8765/`，点页面顶部对应的家族按钮，
下载后在「设置 → 已下载描述文件 → 安装」，再到「设置 → 通用 → 字体」启用。

> 每个家族描述文件内含 18 个静态 TTF。生成物在 `profiles/`（已 gitignore），
> 按需本地生成，不提交仓库。

## 命令行选择字体

`generate_profile.py` 支持灵活指定要打包的字体：

```bash
python generate_profile.py                                        # 默认：全部字体
python generate_profile.py --fonts C:/fonts /x/MyFont.ttf        # 指定目录或单个 ttf 文件
python generate_profile.py --filter Italic                       # 只要斜体（按文件名子串，可多次 OR）
python generate_profile.py --filter Regular --filter Bold        # 只要 Regular 和 Bold
python generate_profile.py --name "我的字体" --out build/out      # 自定义包名与输出目录
python generate_profile.py --pairs                               # 额外生成同字重正体 + 斜体配对包
```

六个字体来源目录可用环境变量覆盖：`HANLINK_FONT_DIR`、
`HANLINK_INTERROBANG_FONT_DIR`、`CJK_PUNCT_FONT_DIR`、
`CJK_PUNCT_INTERROBANG_FONT_DIR`、`INTERROBANG_BRIDGE_FONT_DIR`、
`TH_GROTESK_FONT_DIR`。默认读取相邻仓库的静态输出目录；字体二进制不会复制
或提交到服务器仓库。

> `TH_GROTESK_FONT_DIR` 默认指向 `../ThGrotesk/fonts/static`。iOS 的
> `com.apple.font` 只接受静态字体，所以 Th Grotesk 需要先自行把变量字体
> 实例化成静态 TTF 再放进去；仓库里不含字体文件。

## 服务器接口

| 接口 | 说明 |
| --- | --- |

## 服务器接口

| 接口 | 说明 |
| --- | --- |
| `GET /` | 安装页：全量包、预生成分组包、自定义勾选 |
| `GET /profiles/…` | 预生成的描述文件（`application/x-apple-aspen-config`） |
| `GET /fonts.json` | 可用字体列表（勾选 UI 用） |
| `GET /profiles.json` | 预生成描述文件列表 |
| `POST /api/profile` | 按勾选字体动态生成：`{"fonts":["A.ttf","B.ttf"],"name":"…"}` → 返回 `.mobileconfig` |

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `generate_profile.py` | 描述文件生成器：全量包 + 字重配对包，支持 `--fonts/--filter/--name` |
| `generate_lxgw_profiles.py` | 描述文件生成器：生成落霞孤鹜合集及兼容版描述文件 |
| `server.py` | 局域网服务器：静态描述文件 + 动态生成 API |
| `index.html` | 安装页：全量下载、分组包列表、自定义勾选 |
| 外部字体目录 | 默认读取相邻字体仓库，不在本仓库存放字体 |

字体来源：Hanlink Sans（[Speechlessmanbilibili/Hanlink-Sans](https://github.com/Speechlessmanbilibili/Hanlink-Sans)）、
Hanlink ?!（[Speechlessmanbilibili/Hanlink-Interrobang](https://github.com/Speechlessmanbilibili/Hanlink-Interrobang)）、
CJK Punct Bridge（[Speechlessmanbilibili/CJK-Punct-Bridge](https://github.com/Speechlessmanbilibili/CJK-Punct-Bridge)）与
Th Grotesk（[Speechlessmanbilibili/ThGrotesk](https://github.com/Speechlessmanbilibili/ThGrotesk)）。
## 排障经验：iOS 报「包含无效字体」

以下是本项目的完整排障记录。iOS 的 `com.apple.font` payload 只支持 **base64 内嵌
字体**（无远程 URL 键），报「包含无效字体」通常不是字体本身的问题，而是描述文件
的生成方式。逐条排查，按可能性从高到低：

### 1. 双重 base64 编码（本项目真凶）

`Font` 键**必须传原始字体字节**，由 plistlib 序列化时自行 base64 编码：

```python
"Font": path.read_bytes(),          # ✅ 正确
"Font": base64.b64encode(path.read_bytes()),   # ❌ 双重编码
```

如果先 `b64encode` 一次再交给 plistlib，XML 输出时会被**再编码一次**。
iOS 解码一次后拿到的是 base64 文本而非字体数据，CoreText 加载失败 → 报
「包含无效字体」。二进制 plist 同样中招（存进去的是 base64 文本字节）。
排查时用树级 diff 对比「可用 profile」与「自己的 profile」的 `Font` 值，
立刻就能看出存的是 `\x00\x01\x00\x00`（TTF 魔数）还是 `AAEAAAAR...`（base64 文本）。

### 2. `Name` 键缺失

`com.apple.font` payload 有一个**必需键 `Name`**（值为字体文件名，如
`HanlinkSans-Regular.ttf`），Apple 文档示例和 keyman 实测 profile 中都有。
缺失时 iOS 直接判定「包含无效字体」。注意 `PayloadDisplayName` 不能替代它。

### 3. 服务器不要对 `.mobileconfig` 做 gzip 压缩

Safari 下载描述文件交给系统安装器时可能**不解压**，如果服务器返回
`Content-Encoding: gzip`，安装器拿到的是 gzip 二进制乱码 → 解析失败。
局域网场景直接传原始文件即可（大文件慢一点但正确）。

### 4. Content-Type 只能有一个，且必须正确

必须 `application/x-apple-aspen-config`。注意不要用 `end_headers()` 追加头——
`SimpleHTTPRequestHandler` 已经发过默认的 `application/octet-stream`，追加会
产生**两个 Content-Type 头**，iOS 可能认错。正确做法是覆盖 `extensions_map`：

```python
class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mobileconfig": "application/x-apple-aspen-config",
    }
```

### 5. 关于「15–20MB 描述文件上限」的传言

社区流传 iOS 无法安装大于 15–20MB 的描述文件（如思源宋体 16MB 失败），
但本项目的 189.7MB 全量包（36 个字体）在修复上述问题后**实测一次装成功**。
此前大文件失败很可能也是编码/格式问题，而非大小限制本身。
如果仍担心，可以按字重两两配对生成小包（本项目 `profiles/` 里两种都有）。

### 6. 调试方法论：黄金标准对照实验

找不到头绪时，用「确定可用」的 profile 做黄金标准逐步对照（本项目使用了
[keyman 的字体 profile](https://github.com/keymanapp/r.keymanweb.com)）：

1. **模板替换字体**：把可用 profile 的 `<data>` 替换成自己的字体 ——
   隔离「字体因素」：能装则字体没问题；
2. **重新序列化**：用 plistlib 重新 dump 可用 profile 的全部原值 ——
   隔离「序列化器因素」：能装则 plistlib 输出格式没问题；
3. **单变量修改**：在可用基底上每次只改一个值（identifier、UUID 大小写、
   中文文案等）——逐个排除「值因素」；
4. **树级 diff**：递归对比两棵 plist 的所有键值，最终定位到 `Font` 值
   的编码差异（双重 base64 就是这么抓出来的）。

## 许可证

- 本项目服务器、生成器、页面与文档以 [MIT License](LICENSE) 发布。
- Hanlink Sans、CJK Punct Bridge 与 Th Grotesk 字体仍分别受其字体仓库中的
  [SIL Open Font License 1.1](https://github.com/Speechlessmanbilibili/Hanlink-Sans/blob/main/OFL.txt)
  、[SIL Open Font License 1.1](https://github.com/Speechlessmanbilibili/CJK-Punct-Bridge/blob/main/OFL.txt)
  与 [SIL Open Font License 1.1](https://github.com/Speechlessmanbilibili/ThGrotesk/blob/main/OFL.txt) 约束；MIT 许可证不适用于字体二进制。
- 排障参考了 keyman（[r.keymanweb.com](https://github.com/keymanapp/r.keymanweb.com)）公开的字体描述文件结构
