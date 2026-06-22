---
name: translate-pdf-preserve-layout
description: Translate selectable-text PDF documents with PDFMathTranslate-next/pdf2zh-next while preserving page geometry, formulas, figures, tables, links, annotations, and document structure as far as the upstream engine supports. Use when a user asks to translate a PDF, paper, report, manual, or book and keep the original PDF layout, formatting, or bilingual comparison; also use for requests such as "翻译 PDF 并保持格式不变", "保留排版翻译论文", or "create a bilingual PDF".
---

# Translate PDF While Preserving Layout

Use the bundled wrapper to run [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) safely and predictably without copying its AGPL-3.0 source into the skill. Treat “unchanged format” as preserved page geometry and document elements, not pixel identity: translated text can reflow because languages have different lengths.

## Workflow

1. Inspect the input before translation.
   - Require a readable `.pdf` file and keep the original untouched.
   - Let the wrapper reject truncated or partly downloaded PDFs. If it reports a missing EOF marker or a declared-length mismatch, obtain a complete copy before translating.
   - Determine source and target language codes. Default to `en` -> `zh` only when context provides no better answer.
   - If the PDF is image-only, explain that OCR quality limits fidelity and enable `--auto-enable-ocr-workaround`; do not promise complete OCR recovery.
   - Preserve references and all later content in the source language. The wrapper detects an exact `REFERENCES`, `BIBLIOGRAPHY`, or `参考文献` heading and translates only earlier pages by default. Because upstream page selection is page-based, preserve the entire page containing the heading, including any preceding lines on that page. Never use `--translate-references` unless the user explicitly overrides this requirement.

2. Select a translation service.
   - Honor a service named by the user.
   - Otherwise use `siliconflowfree`, the upstream no-key default.
   - For confidential documents, prefer a user-provided local `ollama`, `claudecode`, or `clitranslator` setup. Remote services receive extracted document text.
   - Put credentials in `PDF2ZH_*` environment variables. Never place API keys directly in the command or logs. Read [provider-config.md](references/provider-config.md) only when configuring a non-default service.

3. Run the wrapper.

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translate-pdf-preserve-layout/scripts/translate_pdf.py" \
  "/absolute/path/input.pdf" \
  --source en --target zh \
  --output-dir "/absolute/path/output" \
  --engine siliconflowfree \
  --mode mono
```

Use `--mode both` when the user wants a translated PDF plus a bilingual comparison. Use `--pages '1-5'` for a requested subset. Run `--check` to verify that a compatible upstream executable is available. The wrapper discovers an installed `pdf2zh-next`; if absent, it falls back to `uvx --from pdf2zh-next` unless `--no-auto-install` is set.

The wrapper disables automatic glossary extraction by default because the no-key service can emit invalid JSON repeatedly on long papers. Enable it with `--auto-extract-glossary` only when a reliable LLM service is configured and terminology consistency needs it. Keep SiliconFlow Free JSON mode off; `--enable-json-mode` is experimental and can cause near-total fallback on long structured papers.

4. Preserve fidelity deliberately.
   - Keep the default `--watermark-mode no_watermark` for the closest match to the source page; select another mode only when requested.
   - With `siliconflowfree`, let the wrapper disable rich-text translation by default. This prevents leaked `<style>`/`<样式>` markers observed in long papers while retaining page geometry, headings, formulas, and figures. Use `--preserve-rich-text` only with deliberate visual review or a more reliable service.
   - Add `--enhance-compatibility` only after a normal run fails or renders badly because it disables rich-text translation.
   - Add `--auto-enable-ocr-workaround` for heavily scanned PDFs.
   - Use `--mode mono` for the same page geometry. Side-by-side dual output intentionally changes page width; alternating dual output intentionally doubles page count.
   - Pass a supported advanced upstream option with repeated `--pdf2zh-arg=VALUE`. Do not use this escape hatch for secrets.

5. Verify every final PDF.
   - Confirm each output opens as a PDF and has nonzero size.
   - For monolingual output, compare page count and representative page dimensions with the source. If only selected pages are included, account for that explicitly.
   - Render and visually compare at least the first page, one text-heavy page, and one formula/table/figure-heavy page when present.
   - Check for clipped or overlapping text, missing glyphs, displaced formulas, damaged figures/tables, lost headings, and unreadable annotations.
   - Extract a short text sample to confirm the target language appears. Do not use text extraction alone as proof of layout fidelity.
   - For scholarly PDFs, compare the title, author names, affiliations, model names, and benchmark names with the source. The no-key service may transliterate personal names even when a glossary asks it not to; use a more reliable configured engine or report this limitation when exact proper-noun preservation matters.
   - Search translated-page text for leaked markup such as `<style ...>` or `<样式 ...>`. The wrapper rejects monolingual output containing these markers.
   - Confirm that the reference-boundary page and every later page contain no newly introduced target-language text. The wrapper also compares their normalized extracted text with the source.
   - Preserve links and annotations. PDFMathTranslate-next may drop page annotations even when the pages look unchanged, so the wrapper copies source annotations back into monolingual output at the same coordinates and verifies the total count. Treat restoration failure as a failed translation. Dual output changes page geometry and does not receive this annotation-restoration guarantee.
   - If a defect appears, retry once with the narrowest relevant compatibility or OCR option, then report any remaining limitation honestly.

6. Deliver the generated PDF paths and state whether each is monolingual or bilingual. Mention any page subset, OCR workaround, or fidelity limitation that affects interpretation.

## Output Convention

PDFMathTranslate-next normally writes `<source>.<target>.mono.pdf` and/or `<source>.<target>.dual.pdf` into the chosen output directory. With the default no-watermark mode, the basename can include `.no_watermark`, as in `<source>.no_watermark.<target>.mono.pdf`. The wrapper prints the concrete files it observed; use those paths rather than guessing.

## Common Failures

- If assets cannot download, retry when network access is available or use upstream offline assets.
- If a service rejects credentials, verify only that the expected `PDF2ZH_*` variable exists; never print its value.
- If translation exits successfully but produces no PDF, treat the run as failed and inspect the upstream log.
- If the output loses links or annotations, ensure `pypdf` is installed; the wrapper requires it to restore and count them.
- If a long paper emits repeated glossary JSON errors, keep the default glossary extraction disabled. If experimental JSON mode produces type/length errors, disable it and allow the upstream simple-translation fallback.
- If style tags leak into translated text, rerun with rich-text translation disabled; this is already the default for `siliconflowfree`.
- If author or institution names are undesirably transliterated, switch to a stronger configured engine or correct them explicitly; do not assume a glossary alone will force the no-key service to preserve them.
- If formulas or tables move, retry with `--enhance-compatibility`; expect simpler typography.
- If a scan contains no text layer, OCR externally when the built-in workaround is insufficient, then rerun the translation.
