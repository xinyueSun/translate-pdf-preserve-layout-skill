# Translate PDF Preserve Layout Skill

一个基于 [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) 的 Codex skill，用于翻译 PDF，并尽可能保留原有页面尺寸、公式、图表、表格、目录、链接、注释和排版结构。

它特别适合论文、技术报告、手册和书籍。默认情况下，skill 会识别 `REFERENCES`、`BIBLIOGRAPHY` 或 `参考文献` 标题，只翻译其之前的页面，参考文献页及其后的附录保持原文。

## 功能

- 调用 PDFMathTranslate-next / `pdf2zh-next` 完成保留版式的 PDF 翻译。
- 支持单语译文和双语对照 PDF。
- 自动拒绝截断、未完整下载或缺少结束标记的 PDF。
- 默认保留参考文献及其后的内容，不进行翻译。
- 为免费翻译服务关闭容易产生异常标记的富文本模式。
- 自动检查页数、页面尺寸、参考文献尾部和翻译标记泄漏。
- 将上游处理时丢失的 PDF 链接和注释恢复到单语译文。
- 支持 SiliconFlow Free、OpenAI、OpenAI Compatible、Ollama、DeepL、Gemini 等翻译服务。

> “保持格式不变”指尽可能保持页面几何尺寸和文档元素，而不是逐像素完全一致。不同语言的文本长度不同，译文仍可能发生合理换行。

## 项目结构

```text
translate-pdf-preserve-layout/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── provider-config.md
└── scripts/
    └── translate_pdf.py
```

## 环境要求

- Python 3.10–3.13
- [uv](https://docs.astral.sh/uv/)（推荐）
- `pdf2zh-next`
- `pypdf`，用于检查 PDF 并恢复链接和注释

安装运行依赖：

```bash
uv tool install pdf2zh-next
python3 -m pip install pypdf
```

如果系统中没有安装 `pdf2zh-next`，包装脚本会尝试通过 `uvx --from pdf2zh-next` 临时运行。

## 安装 Skill

克隆仓库：

```bash
git clone https://github.com/xinyueSun/translate-pdf-preserve-layout-skill.git
cd translate-pdf-preserve-layout-skill
```

复制到 Codex skill 目录：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R translate-pdf-preserve-layout "${CODEX_HOME:-$HOME/.codex}/skills/"
```

如果已经安装过旧版本，请先备份或删除旧的 `translate-pdf-preserve-layout` 目录，再复制新版本。重新打开 Codex 会话后即可使用。

## 在 Codex 中使用

在提示词中明确调用：

```text
使用 $translate-pdf-preserve-layout 将这篇 PDF 翻译成中文并保持原版式。
```

也可以指定输出形式：

```text
使用 $translate-pdf-preserve-layout 把这篇英文论文翻译成中文，生成单语译文；参考文献和附录保持英文。
```

```text
使用 $translate-pdf-preserve-layout 生成中英双语对照 PDF。
```

## 直接运行包装脚本

翻译为中文单语 PDF：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translate-pdf-preserve-layout/scripts/translate_pdf.py" \
  "/absolute/path/input.pdf" \
  --source en \
  --target zh \
  --output-dir "/absolute/path/output" \
  --engine siliconflowfree \
  --mode mono
```

生成单语和双语 PDF：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translate-pdf-preserve-layout/scripts/translate_pdf.py" \
  "/absolute/path/input.pdf" \
  --source en \
  --target zh \
  --output-dir "/absolute/path/output" \
  --engine siliconflowfree \
  --mode both
```

只翻译指定页：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translate-pdf-preserve-layout/scripts/translate_pdf.py" \
  "/absolute/path/input.pdf" \
  --pages "1-5,8" \
  --output-dir "/absolute/path/output"
```

检查运行环境：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translate-pdf-preserve-layout/scripts/translate_pdf.py" --check
```

查看全部选项：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translate-pdf-preserve-layout/scripts/translate_pdf.py" --help
```

## 翻译服务

默认使用无需 API Key 的 `siliconflowfree`。非默认服务的凭据应通过 `PDF2ZH_*` 环境变量提供，不要把密钥直接写入命令行或提交到 Git。

OpenAI 示例：

```bash
export PDF2ZH_OPENAI_API_KEY='...'
export PDF2ZH_OPENAI_MODEL='gpt-4.1-mini'
export PDF2ZH_OPENAI_BASE_URL='https://api.openai.com/v1'
```

然后使用：

```bash
--engine openai
```

更多配置见 [`provider-config.md`](translate-pdf-preserve-layout/references/provider-config.md)。

## 默认行为

- 输出无水印单语 PDF。
- 默认源语言为英语，目标语言为中文。
- 自动检测参考文献标题，并保留该标题所在整页及之后的页面。因此，如果参考文献从页面中部开始，该页标题之前的少量内容也会保持原文。
- 默认关闭自动术语抽取。
- 使用 SiliconFlow Free 时默认关闭富文本翻译，避免输出 `<style>` 或 `<样式>` 标记。
- 单语输出会恢复原 PDF 的链接和注释；双语输出改变了页面几何结构，不提供同等级的注释恢复保证。

## 隐私提示

远程翻译服务会接收从 PDF 中提取的文本。对于保密文件，请使用本地 Ollama、Claude Code、CLI Translator，或组织允许的私有翻译端点。

## 已知限制

- 扫描型 PDF 依赖 OCR，识别质量会影响译文和排版。
- 免费服务可能音译作者姓名、机构名或其他专有名词。
- 复杂数学公式、跨栏表格或极端字体仍可能需要人工复核。
- 双语 PDF 会改变页宽或页数，不可能与原文件保持相同页面几何尺寸。
- PDF 数字签名在内容重写后通常会失效。

## 许可证

本仓库中的原创代码和文档采用 [MIT License](LICENSE)。

本项目通过命令行调用 PDFMathTranslate-next，但不包含其源代码。PDFMathTranslate-next 是独立的上游项目，采用 [AGPL-3.0](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next/blob/main/LICENSE) 许可证；安装、使用或分发该依赖时，请同时遵守其许可证要求。
