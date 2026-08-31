# Xiumi Native Clipboard

把一篇完整稿件保存为自包含的 `.xiumi.json`，在浏览器中预览，然后以秀米原生组件格式复制粘贴。图片、文字、横排、卡片和出框插画都会作为可继续编辑的组件进入秀米，不依赖 HTML 导入。

在线工具：<https://gih10012.github.io/xiumi-native-clipboard/>

## 使用

1. 用桌面版 Edge 或 Chrome 打开在线工具。
2. 选择或拖入 `.xiumi.json` 文件。
3. 检查预览，在页面内真实按下 `Ctrl+C`。
4. 回到秀米编辑器按 `Ctrl+V`。

文章和图片只在本地浏览器中解析；选择本地文件不会上传内容。

如果希望网址打开时已经选好本机 JSON，使用零依赖本地服务：

```bash
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json
```

命令会打印形如 `http://127.0.0.1:PORT/?src=...&copy=...` 的地址。这个本机网址不仅会自动载入稿件，还能让“复制到秀米”按钮通过 `wl-copy` 或 `xclip` 直接写入 Chromium 私有剪切板；若系统没有可用的剪切板工具，页面会提示改用真实 `Ctrl+C`。服务仅监听本机回环地址，不会上传或缓存稿件。

## CLI

```bash
# 校验整体 JSON
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py validate ARTICLE.xiumi.json

# 生成 chromium/x-web-custom-data 对应的 DataTransfer 二进制
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py pack ARTICLE.xiumi.json -o ARTICLE.bin

# 反向解析以排查兼容问题
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py unpack ARTICLE.bin -o ROUNDTRIP.xiumi.json
```

运行时只有 Python 标准库。格式定义见 [`schema/xiumi-document.schema.json`](schema/xiumi-document.schema.json)，可复用的组件构造器位于 Skill 的 `scripts/xiumi_components.py`。

## 安装 Codex Skill

克隆仓库后，将技能目录链接到 Codex 的技能目录：

```bash
ln -s "$(pwd)/skills/xiumi-native-clipboard" ~/.codex/skills/xiumi-native-clipboard
```

之后可直接要求 Codex 生成秀米原生 JSON 并提供已预载的本机预览网址。真实文章、Base64 图片和秀米 UID 不应提交到公共仓库。

## 兼容性

复制过程使用 Chromium 的 DataTransfer 自定义格式，由真实 `Ctrl+C` 生成秀米能够读取的私有剪切板容器。本地服务的按钮提供等价的系统剪切板桥接。首版目标为桌面版 Edge/Chrome；Firefox 和 Safari 不在兼容范围内。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
node tests/browser_smoke.mjs examples/demo.xiumi.json
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/xiumi-native-clipboard
```

## License

MIT
