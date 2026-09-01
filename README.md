# Xiumi Native Clipboard

把一篇完整稿件保存为自包含的 `.xiumi.json`，在浏览器中预览，再以秀米原生组件格式复制粘贴。图片先由秀米上传到当前账号的图库，排版随后作为可继续编辑的原生组件进入秀米；这样既不依赖 HTML 导入，也不会再出现“能粘贴但不能保存”的 Base64 图片稿。

在线工具：<https://gih10012.github.io/xiumi-native-clipboard/>

## 使用

1. 用桌面版 Edge 或 Chrome 打开在线工具。
2. 选择或拖入 `.xiumi.json` 文件。
3. 如果页面显示“待本地化”，点击“① 复制图片上传单”，再在页面内真实按下 `Ctrl+C`。
4. 把上传单粘贴到一个空白秀米临时稿。等图片出现后，在秀米中复制临时稿全文。
5. 回到工具按 `Ctrl+V`。页面显示“保存就绪”后，可下载已持久化的 JSON。
6. 点击“② 复制保存版到秀米”，或按页面提示真实按下 `Ctrl+C`，再到目标秀米稿按 `Ctrl+V`。

没有图片或图片已经是持久化网址时，会直接进入“保存就绪”，可跳过上传单。

选择本地文件时，文章和图片只在本地浏览器中解析。只有你把“图片上传单”粘贴到秀米时，图片才会上传到当前登录的秀米账号。

如果希望网址打开时已经选好本机 JSON，使用零依赖本地服务：

```bash
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json
```

命令会打印形如 `http://127.0.0.1:PORT/?src=...&copy=...` 的地址。这个本机网址会自动载入稿件；图片完成持久化后，“复制保存版到秀米”按钮可通过 `wl-copy` 或 `xclip` 写入 Chromium 私有剪切板。上传单仍需在浏览器页面中用真实 `Ctrl+C` 复制。服务仅监听本机回环地址，不会上传或缓存稿件。

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

克隆仓库后，将技能目录链接到 Codex 的技能目录：

```bash
ln -s "$(pwd)/skills/xiumi-native-clipboard" ~/.codex/skills/xiumi-native-clipboard
```

之后可直接要求 Codex 生成秀米原生 JSON 并提供已预载的本机预览网址。真实文章、Base64 图片和秀米 UID 不应提交到公共仓库。

## 兼容性

最终复制使用 Chromium 的 DataTransfer 自定义格式，由真实 `Ctrl+C` 生成秀米能够读取的私有剪切板容器。本地服务的按钮提供等价的系统剪切板桥接。Base64 图片不能直接走这条路径：秀米会跳过图片上传，因此工具会先用普通 `text/html` 上传单完成图片持久化，再恢复原生组件复制。目标浏览器为桌面版 Edge/Chrome；Firefox 和 Safari 不在兼容范围内。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
node tests/browser_smoke.mjs examples/demo.xiumi.json
node tests/browser_smoke.mjs examples/image-draft.xiumi.json
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/xiumi-native-clipboard
```

## License

MIT
