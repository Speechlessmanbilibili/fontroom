# iOS 字体安装服务器 (ios-font-server) — 项目架构与技术指引

本文档梳理了本项目的整体架构、设计考量以及在 iOS 字体描述文件生成与分发过程中总结出的技术经验，供协作开发与功能扩展时参考。

---

## 项目概况与资产约定

本项目的核心功能是通过 Python 局域网服务向同一 Wi-Fi 网络下的 iPhone 与 iPad 设备分发 iOS 配置描述文件（`.mobileconfig`），实现字体免越狱无线安装。

相关的工程约定如下：

1. **资产与版本控制管理**：字体二进制文件（`.ttf`、`.otf` 等）体积较大且多涉及字库版权，生成的描述文件（`profiles/`）体积通常在数兆至数百兆之间，属于本地构建产物。因此字体目录与生成物均在 `.gitignore` 中忽略，远端仓库配置为私有（Private）。
2. **提交记录风格**：Git Commit Message 采用清晰、准确的纯中文简述概括功能变动即可，通常不附带多余的自动化署名或免责声明。

---

## 描述文件生成原理与排障经验

在生成 iOS 描述文件与网络分发过程中，由于 iOS 系统和 CoreText 引擎对描述文件的结构和传输方式有特定要求，以下是在实际调试中总结的要点：

### 1. 字体数据的二进制写入机制
iOS 的 `com.apple.font` Payload 支持将字体以二进制形式内嵌在描述文件中。在 Python 中通过 `plistlib.dumps(..., fmt=plistlib.FMT_BINARY)` 构建二进制 plist 时，`Font` 键传入原始字体字节流（`path.read_bytes()`）即可由序列化器完成封装。
如果提前对字体字节进行 Base64 编码，写入 plist 后会导致数据被二次编码。客户端下载解码后获取到的是 Base64 文本而非字体的二进制魔数（如 `\x00\x01\x00\x00`），从而引发 CoreText 报错并提示「包含无效字体」。

### 2. Payload 中的 Name 键
Apple 对字体 Payload 的解析要求包含 `Name` 键，其值对应为字体的真实文件名（如 `HanlinkSans-Regular.ttf` 或 `ThGrotesk-SemiBold.ttf`）。
`PayloadDisplayName` 仅用于安装界面与设置列表中的展示，不能替代 `Name` 键。缺少该键会导致描述文件被系统判定为无效。

### 3. 局域网传输中的 Gzip 处理
Safari 在局域网中下载描述文件并唤起系统安装器时，安装器通常不会自动解压带有 `Content-Encoding: gzip` 的数据流，而是将压缩二进制直接作为 plist 尝试解析。因此服务端对于 `.mobileconfig` 文件采用未压缩的原始流进行传输更为可靠。

### 4. Content-Type 标头规范
iOS 对描述文件依赖 MIME 类型 `application/x-apple-aspen-config` 进行识别。在基于 Python 的 HTTP 服务中，通过覆盖 `extensions_map` 输出单一明确的 Content-Type，可以避免默认处理器追加通用类型导致双重标头的问题。

### 5. 文件生成的原子替换
当打包较多字形时，描述文件体积较大。采用先写临时文件（如 `.tmp.mobileconfig`）再通过原子替换（`replace`）覆盖目标文件的流程，能够避免移动端在生成尚未结束时拉取到不完整文件。

---

## 架构布局与各模块职责

项目的核心目录与文件布局如下：

```
ios-font-profile/
├── generate_profile.py             # 核心生成库与命令行工具，组装 plist 并处理显示名称
├── generate_lxgw_profiles.py       # 落霞孤鹜字体合集生成器，处理原版合集与 Word 兼容版
├── generate_lxgw_compatible_fonts.py # 字体元数据处理工具，调整 PostScript Name
├── server.py                       # 局域网服务主程序，提供页面托管与动态生成接口
├── index.html                      # 手机端安装页面，提供家族包、合集包与自选面板
├── profiles/                       # 本地生成的描述文件存放目录（已在 gitignore 中忽略）
├── fonts/                          # 本地字体临时副本目录（已在 gitignore 中忽略）
├── tests/                          # 自动化测试用例
│   └── test_generate_profile.py    # 基础生成逻辑与字体显示名称解析测试
├── README.md                       # 面向终端用户的使用说明与排障总结
└── AGENTS.md                       # 面向工程协作的架构指引与技术备忘
```

### 各模块职责划分

1. **`generate_profile.py`**：
   - 核心组装逻辑：`make_profile` 函数负责构建 Configuration Profile 数据结构，分配 Payload UUID 并划分标识符命名空间。
   - 显示名称解析：`display_name(path)` 按文件名前缀将磁盘文件映射为便于阅读的名称。
   - 基础来源定义：`DEFAULT_FONT_DIRS` 默认对应 6 个相邻静态字体目录，与既有单元测试保持一致。

2. **`server.py`**：
   - 使用多线程 TCP 服务（`ThreadingTCPServer`），启动时输出可用的局域网 IP 地址。
   - 端口按候选列表依次尝试，避开 Windows Hyper-V/WSL 的 TCP 保留区间。
   - 通过 `GET /profiles.json` 与 `GET /fonts.json` 为前端提供列表，并通过 `POST /api/profile` 支持动态生成自定义字体包。

3. **`index.html`**：
   - 针对移动端 Safari 触摸与展示优化的单页界面。
   - 包含独立字体家族卡片区、预生成合集包下载区（配合 `COLLECTION_DESCS` 显示说明），以及带快捷芯片筛选的高级自选字体面板。

---

## 常用工作流与调试说明

在 Windows 环境下运行 Python 脚本时，建议统一开启 UTF-8 模式（添加 `-X utf8` 参数），避免终端在输出中文名称或处理路径时发生编码异常。

### 1. 运行测试套件
```pwsh
python -X utf8 -m unittest discover tests
```

### 2. 生成描述文件
```pwsh
# 生成相邻字体仓库的六个静态家族描述文件
python -X utf8 generate_profile.py

# 生成落霞孤鹜系列描述文件（原版与 Word 兼容版）
python -X utf8 generate_lxgw_profiles.py
```

### 3. 启动局域网服务
```pwsh
python -X utf8 server.py
```
服务启动后控制台会显示可用的局域网地址，通过同一局域网下的手机 Safari 访问相应地址即可进行下载和安装调试。
