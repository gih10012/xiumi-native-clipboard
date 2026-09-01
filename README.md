# Xiumi Native Clipboard

把一篇完整稿件保存为自包含的 `.xiumi.json`，在浏览器中预览并交付给秀米。默认先复制包含完整排版和图片的 HTML，让秀米在一次粘贴中上传图片并生成可保存正文；只有需要更高的原生组件还原度时，才进行可选的 `xiumi-comps` 覆盖。

在线工具：<https://gih10012.github.io/xiumi-native-clipboard/>

## 使用

1. 用桌面版 Edge 或 Chrome 打开在线工具。
2. 选择或拖入 `.xiumi.json` 文件。
3. 点击“① 复制带格式 HTML”，在页面内真实按下 `Ctrl+C`，再到秀米按 `Ctrl+V`。完整排版与图片会一起导入；等图片加载完成后，这一版已经可以直接保存。
4. 如果 HTML 版效果满意，到此结束。
5. 如果还需要原生组件：在秀米全选并复制刚导入的正文，回到工具按 `Ctrl+V`。工具取得秀米的永久图片地址后会解锁“② 复制 xiumi-comps（可选）”。
6. 复制②，回秀米全选第一步的正文，再粘贴一次；原生组件会覆盖 HTML 版，而不是追加到末尾。

选择本地文件时，文章和图片只在本地浏览器中解析。只有把①粘贴到秀米时，图片才会上传到当前登录的秀米账号。

如果希望网址打开时已经选好本机 JSON，使用零依赖本地服务：

```bash
python3 skills/xiumi-native-clipboard/scripts/xiumi_clipboard.py serve ARTICLE.xiumi.json
```

命令会打印形如 `http://127.0.0.1:PORT/?src=...&copy=...` 的地址。这个本机网址会自动载入稿件；②解锁后，本地按钮可通过 `wl-copy` 或 `xclip` 写入 Chromium 私有剪切板。①仍需在浏览器页面中用真实 `Ctrl+C` 复制。服务仅监听本机回环地址，不会上传或缓存稿件。

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

①只写入 `text/html` 与 `text/plain`，因此秀米会执行普通 HTML 粘贴并上传 Base64 图片。②使用 Chromium DataTransfer 自定义格式；因为其中的图片地址已经从第一步的秀米正文回传，所以能够保存。本地服务的按钮为②提供等价的系统剪切板桥接。目标浏览器为桌面版 Edge/Chrome；Firefox 和 Safari 不在兼容范围内。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
node tests/browser_smoke.mjs examples/demo.xiumi.json
node tests/browser_smoke.mjs examples/image-draft.xiumi.json
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/xiumi-native-clipboard
```

## License

MIT
