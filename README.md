# Xiumi Native Clipboard

把一篇完整稿件保存为自包含的 `.xiumi.json`，在浏览器中预览并交付给秀米。含本地图片的稿件分两轮交付：第一轮只把全部图片交给秀米上传，第二轮再用已经持久化的图片地址生成完整原生正文。

在线工具：<https://gih10012.github.io/xiumi-native-clipboard/>

## 使用

1. 用桌面版 Edge 或 Chrome 打开在线工具。
2. 选择或拖入 `.xiumi.json` 文件。
3. 点击“① 复制全部图片（无格式）”，在页面内真实按下 `Ctrl+C`，再粘贴到一个空白秀米临时稿。第一轮故意不含标题、文字和正式排版，只应出现全部图片。
4. 等秀米的粘贴和上传提示完全结束，使用秀米的“复制全文”。回到工具按 `Ctrl+V`；工具取得全部永久图片地址后会解锁②。
5. 点击“② 复制 xiumi-comps（生成正文）”。若打开的是在线工具，再在本页真实按一次 `Ctrl+C`；若使用本地服务，按钮会直接写入剪切板。
6. 到一个空白秀米正式稿按 `Ctrl+V`，一次生成标题、文字、图片和完整原生排版。第一轮的临时图片稿可以丢弃。

选择本地文件时，文章和图片只在本地浏览器中解析。只有把①粘贴到秀米时，图片才会上传到当前登录的秀米账号。

如果希望网址打开时已经选好本机 JSON，使用零依赖本地服务：

```bash
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json
```

命令会打印形如 `http://127.0.0.1:PORT/?src=...&copy=...` 的地址。这个本机网址会自动载入稿件。Linux 下，②解锁后本地按钮可通过 `wl-copy` 或 `xclip` 写入 Chromium 私有剪切板；Windows 和 macOS 会自动回退为页面内真实 `Ctrl+C`。①在三端都需使用页面内真实复制。服务仅监听本机回环地址，不会上传或缓存稿件。

## CLI

```bash
# 校验整体 JSON
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json

# 最终交付前校验：存在 Base64 草稿图片时会失败
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py validate ARTICLE.save-ready.xiumi.json --save-ready

# 只为保存就绪稿生成 chromium/x-web-custom-data 二进制
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py pack ARTICLE.xiumi.json -o ARTICLE.bin

# 仅供协议排查：允许打包不可保存的内嵌图片草稿
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py pack ARTICLE.xiumi.json -o DRAFT.bin --allow-embedded-draft

# 反向解析以排查兼容问题
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py unpack ARTICLE.bin -o ROUNDTRIP.xiumi.json
```

运行时只有 Python 标准库。格式定义见 [`schema/xiumi-document.schema.json`](schema/xiumi-document.schema.json)，可复用的组件构造器位于 Skill 的 `scripts/xiumi_components.py`。

## 安装 Codex Skill

最省事的方式是让另一个 Codex 使用内置的 `skill-installer`，从仓库子目录 `skills/xiumi-native-clipboard` 安装。手动安装时，macOS/Linux 可克隆后建立链接：

```bash
ln -s "$(pwd)/skills/xiumi-native-clipboard" ~/.codex/skills/xiumi-native-clipboard
```

Windows PowerShell 可复制技能目录：

```powershell
git clone https://github.com/gih10012/xiumi-native-clipboard.git
New-Item -ItemType Directory -Force "$HOME\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\xiumi-native-clipboard\skills\xiumi-native-clipboard" "$HOME\.codex\skills\xiumi-native-clipboard"
```

之后可直接要求 Codex 生成秀米原生 JSON 并提供已预载的本机预览网址。真实文章、Base64 图片和秀米 UID 不应提交到公共仓库。

## 兼容性

①只写入 `text/html` 与 `text/plain`：HTML 是无文字上传单，不包含正式稿的任何文字或布局。秀米当前的 Base64 图片扫描会稳定出现一次成功、一次失败的交替结果，因此工具让每张 Base64 真实图片后面跟随一个唯一的透明图片标记，由标记承担失败；回传时再自动剔除标记。②使用 Chromium DataTransfer 自定义格式；其中的真实图片地址已从临时图片稿回传为秀米永久地址，因此完整原生正文能够保存。本地服务的按钮为②提供等价的系统剪切板桥接。目标浏览器为桌面版 Edge/Chrome；Firefox 和 Safari 不在兼容范围内。

| 环境 | 在线工具 / 页面内 `Ctrl+C` | 本地②一键桥接 |
| --- | --- | --- |
| Windows 10/11 + Edge/Chrome | 支持 | 自动回退为页面内 `Ctrl+C` |
| macOS + Edge/Chrome | 支持 | 自动回退为页面内 `Ctrl+C` |
| Linux Wayland/X11 + Edge/Chrome/Chromium | 支持 | 安装 `wl-copy` 或 `xclip` 后支持 |
| Android、iOS、Firefox、Safari | 不支持 | 不支持 |

因此它支持三大桌面系统，但不是所有浏览器和移动平台通用。Python 的校验、打包、反解和本地预览服务在 Windows、macOS、Linux CI 中测试；真实 Chromium 私有剪切板冒烟测试目前在 Linux CI 中运行。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
node tests/browser_smoke.mjs examples/demo.xiumi.json
node tests/browser_smoke.mjs examples/image-draft.xiumi.json
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/xiumi-native-clipboard
```

## License

MIT
