# iOS 字体安装服务器

在 iOS 上安装中文字体，常见的做法是借助一类运行在手机上的字体管理应用。典型流程是：先把字体文件传到手机，在应用里导入并勾选，然后点击“安装”，由应用生成配置描述文件并调起系统浏览器的小窗完成下载。

这套流程容易卡在最后一步：

- **点击“安装”的那一瞬间直接闪退**，字体来不及下发；
- **单个字体体积越大越容易触发**；
- **一次勾选的字体总量越大越容易触发**；
- 此外，勾选本身需要在应用内逐条点选，装入多款时相当繁琐。

失败集中在这条流程的最后一步：描述文件由应用生成，并由应用调起浏览器小窗。上述几处现象都出现在这一环节，而非 iOS 自身的描述文件能力。

本项目换一条路径，整条链路里没有应用：电脑端作为静态服务器托管描述文件，手机用系统自带的浏览器访问并下载，再由系统完成安装。该环节因此不复存在，与原流程的失败点无关。

- **不生成、不中转。** 描述文件在电脑侧生成完毕，以静态文件形式提供，应用不参与任何一步。
- **单个文件可以承载整个字体族。** 默认配置为每个家族 9 个正体与 9 个斜体，共 18 个静态 TTF；实测上百兆的单包同样可以一次安装完成（见排障附录第 5 节）。
- **字体数据以二进制内嵌在描述文件中**，不存在远程字体地址，安装与运行均不依赖外部服务；从生成、下载到安装，数据不出局域网。

## 快速开始

```bash
pip install fonttools

# 1. 生成描述文件（默认扫描相邻字体仓库的六个静态目录）
python generate_profile.py

# 2. 启动局域网服务器
python server.py
```

手机 Safari 打开控制台输出的局域网地址，点击页面顶部对应的家族按钮下载描述文件，随后在“设置 → 已下载描述文件 → 安装”，再到“设置 → 通用 → 字体”确认启用。

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

## 排障附录：iOS 报“包含无效字体”

以下记录的是一次完整排障过程。iOS 的 `com.apple.font` payload 只支持 **base64 内嵌字体**（不存在远程 URL 键），而当系统报“包含无效字体”时，原因通常不在字体本身，而在描述文件的生成方式。以下按可能性从高到低排列。

### 1. 双重 base64 编码

`Font` 键**必须传原始字体字节**，由 plistlib 序列化时自行完成 base64 编码：

```python
"Font": path.read_bytes(),                      # 正确
"Font": base64.b64encode(path.read_bytes()),    # 错误：双重编码
```

若先 `b64encode` 一次再交给 plistlib，XML 输出时会被再编码一次。iOS 解码后得到的是 base64 文本而非字体数据，CoreText 加载失败，随即报“包含无效字体”。二进制 plist 同样会中招（存进去的是 base64 文本字节）。

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

### 5. 描述文件体积上限的实测数据

社区流传 iOS 无法安装大于 15–20 MB 的描述文件，常被引用的例子是 16 MB 的思源宋体安装失败。但本项目 189.7 MB 的全量包（36 个字体）在修复上述问题后**实测一次安装成功**。此前大文件的失败，很可能同样是编码或格式问题，而非 15–20 MB 这个数量级的限制。

真正的上限在几百兆这个量级。下面这组数据来自思源宋体，指的是二进制 plist 的最终体积，不是字体文件的原始大小：

| 描述文件体积 | 内含字体数 | 结果 |
| --- | --- | --- |
| 161.7 MB | 7 | 装成功 |
| 323.4 MB | 14 | 装成功 |
| 485.3 MB | 21 | 装成功 |
| 646.9 MB | 28 | **装失败** |
| 808.6 MB | 35 | **装失败** |

失败时的系统提示是“序列文件无法被反序列化”，iPad 上则直接提示安装失败。**两个提示都出现在下载完成之后**，说明数据已经完整送达，是系统在解析阶段拒绝。同一批包在体积略小的情况下可以正常安装，因此这不是网络传输中断，也不是存储空间不足，而是解析环节存在上限。

工程上取 **500 MB 作为安全线**比较稳妥。单份描述文件控制在这个数值以内可以装成功；超过之后即使只多出 160 MB 也会被拒绝。

需要装更多字体时，按用途拆成多份分次安装即可，iOS 支持同时安装多个描述文件。本项目就是把思源宋体按语言版本拆开的，简繁港一份、日韩一份。

如果单个包仍然偏大，也可以按字重两两配对生成小包，本项目 `profiles/` 目录下两种形式都保留着。

另外一条无伤大雅但值得补齐的细节：Python 3.13 的 `SimpleHTTPRequestHandler` 没有实现 Range，`send_head` 里完全不看 `Range` 头，响应里也没有 `Accept-Ranges`，`copyfile` 则没有用上 `sendfile`。补它的理由是这属于 HTTP 的标准行为，缺了会让部分客户端在探测分片下载时行为异常，而按规范返回 206 与 `Content-Range` 只是几十行代码。需要说明的是，**它对 iOS 下载中断没有实际帮助**，原因见下一节。

### 6. Safari 下载大文件的限制

下载和安装是两层独立的问题，排查时必须分开确认。**上面那张表里所有失败的包，下载都是完整的**，进度条走到底，Safari 里能看到文件已完成，报错发生在随后进入安装界面的时候。所以体积问题只影响解析环节，不影响传输。

下载这一侧另有限制，是社区反复报告且本项目也遇到过的：

- **超过 600 MB 的下载容易失败**，失败之后 Safari 不会续传，重新点击是从头开始；
- **下载期间 Safari 必须保持在前台**。锁屏或切到其他应用，iOS 的内存管理会回收 Safari，下载就停在那里。

本项目实测 161 MB、323 MB、485 MB 三档都能稳定下完，所以真正要控制的是**把描述文件体积压在上限以内**，而不是指望传输层的续传能力。

顺带一条容易踩的坑：客户端中途断开时，Windows 抛的是 `ConnectionAbortedError`（WinError 10053），Linux 抛的是 `ConnectionResetError`（10054）或 `BrokenPipeError`。只捕获后两种的话，Windows 上每次断连都会往日志里打一整段堆栈，看起来像服务端出了故障，实际只是客户端不再接收数据。统一捕获 `OSError` 即可，这三者都是它的子类。

**这一段是本项目走过弯路的地方，值得单独提醒。** 初期看到下载中途断开的日志，会顺势认为瓶颈在传输，于是去调发送缓冲区、关 Nagle、补 Range。这些改动本身没有害处，但都没有解决问题，因为真正卡住的是另外两件事：解析环节的体积上限，以及 Safari 自身对大文件下载的限制。

排查这类问题时，应该先把三个环节分开确认，别混在一起：

1. **传输是否完整**（进度条有没有走到底）
2. **解析是否通过**（设置里能不能看到待安装项）
3. **上限在哪里**（逐档加体积，找到第一档失败的）

本项目当初就是把第一和第二件事混成了“大文件下不完”，白白绕了几轮。

### 7. 调试方法论：黄金标准对照

找不到头绪时，用一份“确定可用”的 profile 作为黄金标准逐步对照（本项目采用了 [keyman 的字体 profile](https://github.com/keymanapp/r.keymanweb.com)）：

1. **模板替换字体**：把可用 profile 的字体数据替换成自己的——用于隔离“字体因素”，能装则说明字体没有问题；
2. **重新序列化**：用 plistlib 重新 dump 可用 profile 的全部原值——用于隔离“序列化器因素”，能装则说明 plistlib 的输出格式没有问题；
3. **单变量修改**：在可用基底上每次只改一个值（identifier、UUID 大小写、中文文案等）——逐个排除“值因素”；
4. **树级 diff**：递归对比两棵 plist 的所有键值。本项目最终正是靠这一步定位到 `Font` 值的编码差异。

## 许可证

- 本项目的服务器、生成器、页面与文档以 [MIT License](LICENSE) 发布。
- 字体来源仓库中的字体分别受其自身的 [SIL Open Font License 1.1](https://github.com/Speechlessmanbilibili/Hanlink-Sans/blob/main/OFL.txt) 约束；MIT 许可证不适用于字体二进制。
- 排障过程参考了 keyman 公开的字体描述文件结构。
