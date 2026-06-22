#!/usr/bin/env python3
"""Safe wrapper around PDFMathTranslate-next's pdf2zh-next command line."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ENGINES = (
    "siliconflowfree",
    "google",
    "bing",
    "openai",
    "aliyundashscope",
    "deepl",
    "deepseek",
    "ollama",
    "xinference",
    "azureopenai",
    "modelscope",
    "zhipu",
    "siliconflow",
    "tencentmechinetranslation",
    "gemini",
    "azure",
    "anythingllm",
    "dify",
    "grok",
    "groq",
    "qwenmt",
    "openaicompatible",
    "claudecode",
    "clitranslator",
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Translate a PDF with pdf2zh-next while preserving its layout.",
    )
    p.add_argument("input_pdf", nargs="?", type=Path)
    p.add_argument("--source", default="en", help="Source language code (default: en)")
    p.add_argument("--target", default="zh", help="Target language code (default: zh)")
    p.add_argument("--output-dir", type=Path, help="Output directory")
    p.add_argument("--engine", choices=ENGINES, default="siliconflowfree")
    p.add_argument("--mode", choices=("mono", "dual", "both"), default="mono")
    p.add_argument("--pages", help="Page selection such as 1-5,8")
    p.add_argument(
        "--translate-references",
        action="store_true",
        help="Translate references and later content instead of preserving them",
    )
    p.add_argument(
        "--watermark-mode",
        choices=("watermarked", "no_watermark", "both"),
        default="no_watermark",
    )
    p.add_argument("--qps", type=int, help="Translation service request limit")
    p.add_argument("--enhance-compatibility", action="store_true")
    p.add_argument(
        "--preserve-rich-text",
        action="store_true",
        help="Keep rich-text translation with SiliconFlow Free (may leak style tags)",
    )
    p.add_argument("--auto-enable-ocr-workaround", action="store_true")
    p.add_argument("--alternating-dual", action="store_true")
    p.add_argument("--only-include-translated-page", action="store_true")
    p.add_argument(
        "--auto-extract-glossary",
        action="store_true",
        help="Enable upstream automatic glossary extraction (disabled by default)",
    )
    p.add_argument(
        "--enable-json-mode",
        action="store_true",
        help="Request JSON mode from the SiliconFlow Free service (experimental)",
    )
    p.add_argument(
        "--pdf2zh-arg",
        action="append",
        default=[],
        metavar="VALUE",
        help="Pass one additional argument token to pdf2zh-next; repeat as needed",
    )
    p.add_argument("--runner", type=Path, help="Explicit pdf2zh-next executable")
    p.add_argument("--no-auto-install", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Print a redacted command only")
    p.add_argument("--check", action="store_true", help="Check the upstream runtime and exit")
    return p


def executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find_runner(explicit: Path | None, auto_install: bool) -> list[str]:
    if explicit:
        candidate = explicit.expanduser().resolve()
        if not executable(candidate):
            raise RuntimeError(f"Runner is not executable: {candidate}")
        return [str(candidate)]

    for name in ("pdf2zh_next", "pdf2zh2", "pdf2zh"):
        found = shutil.which(name)
        if found:
            return [found]

    local_bin = Path.home() / ".local" / "bin"
    for name in ("pdf2zh_next", "pdf2zh2", "pdf2zh"):
        candidate = local_bin / name
        if executable(candidate):
            return [str(candidate)]

    if auto_install:
        uvx = shutil.which("uvx")
        if uvx:
            return [uvx, "--from", "pdf2zh-next", "pdf2zh_next"]
        uv = shutil.which("uv")
        if uv:
            return [uv, "tool", "run", "--from", "pdf2zh-next", "pdf2zh_next"]

    raise RuntimeError(
        "pdf2zh-next was not found. Install it with `uv tool install pdf2zh-next` "
        "or make uvx available."
    )


def snapshot(directory: Path) -> dict[Path, tuple[int, int]]:
    result = {}
    for path in directory.glob("*.pdf"):
        try:
            stat = path.stat()
        except OSError:
            continue
        result[path.resolve()] = (stat.st_mtime_ns, stat.st_size)
    return result


def pdf_integrity_error(path: Path) -> str | None:
    try:
        size = path.stat().st_size
        if size < 5:
            return "file is empty or too small"
        with path.open("rb") as handle:
            head = handle.read(min(size, 8192))
            handle.seek(max(0, size - 65536))
            tail = handle.read()
        if not head.startswith(b"%PDF-"):
            return "missing PDF header"
        if b"%%EOF" not in tail:
            return "missing PDF end marker; the file may be truncated or not fully downloaded"
        linearized_length = re.search(
            rb"/Linearized\s+1\b.{0,1024}?/L\s+(\d+)", head, re.DOTALL
        )
        if linearized_length:
            declared = int(linearized_length.group(1))
            if declared > size + 1024:
                return (
                    f"linearized PDF declares {declared} bytes but only {size} bytes "
                    "are present; the file is truncated"
                )
        return None
    except OSError as exc:
        return f"cannot read PDF: {exc}"


def valid_pdf(path: Path) -> bool:
    return pdf_integrity_error(path) is None


def find_pdftotext() -> str | None:
    found = shutil.which("pdftotext")
    if found:
        return found
    candidates = [
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pdftotext",
        Path("/opt/homebrew/bin/pdftotext"),
        Path("/usr/local/bin/pdftotext"),
        Path("/usr/bin/pdftotext"),
    ]
    return next((str(path) for path in candidates if executable(path)), None)


def extract_page_texts(path: Path) -> tuple[list[str], list[tuple[float, float]]]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path), strict=False)
        texts = [(page.extract_text() or "") for page in reader.pages]
        sizes = [
            (float(page.mediabox.width), float(page.mediabox.height))
            for page in reader.pages
        ]
        return texts, sizes
    except (ImportError, OSError, ValueError):
        pass

    pdftotext = find_pdftotext()
    if not pdftotext:
        raise RuntimeError(
            "Cannot inspect PDF text. Install pypdf or Poppler's pdftotext."
        )
    completed = subprocess.run(
        [pdftotext, "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"pdftotext could not inspect {path}")
    return completed.stdout.split("\f"), []


def find_reference_start(texts: list[str]) -> int | None:
    heading = re.compile(r"^(references|bibliography|参考文献)$", re.IGNORECASE)
    for page_number, text in enumerate(texts, 1):
        if any(heading.fullmatch(line.strip()) for line in text.splitlines()):
            return page_number
    return None


def selected_pages(spec: str, page_count: int) -> set[int]:
    pages: set[int] = set()
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        if "-" not in token:
            pages.add(int(token))
            continue
        start_text, end_text = token.split("-", 1)
        start = int(start_text) if start_text else 1
        end = int(end_text) if end_text else page_count
        if start > end:
            raise ValueError(f"invalid page range: {token}")
        pages.update(range(start, end + 1))
    if not pages or min(pages) < 1 or max(pages) > page_count:
        raise ValueError(f"page selection must stay within 1-{page_count}")
    return pages


def normalized_text(text: str) -> str:
    return re.sub(r"[\s\x00-\x1f]+", "", text)


def annotation_count(path: Path) -> int:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path), strict=False)
        total = 0
        for page in reader.pages:
            annotations = page.get("/Annots")
            if annotations is None:
                continue
            if hasattr(annotations, "get_object"):
                annotations = annotations.get_object()
            if isinstance(annotations, list):
                total += len(annotations)
        return total
    except (ImportError, OSError, ValueError) as exc:
        raise RuntimeError(f"cannot inspect PDF annotations: {exc}") from exc


def restore_annotations(source: Path, output: Path) -> int:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import NameObject
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required to preserve PDF links and annotations"
        ) from exc

    try:
        source_reader = PdfReader(str(source), strict=False)
        output_reader = PdfReader(str(output), strict=False)
        if len(source_reader.pages) != len(output_reader.pages):
            raise RuntimeError("cannot restore annotations when page counts differ")

        pages_with_annotations = []
        expected_count = 0
        for index, page in enumerate(source_reader.pages):
            annotations = page.get("/Annots")
            if annotations is None:
                continue
            resolved = (
                annotations.get_object()
                if hasattr(annotations, "get_object")
                else annotations
            )
            if isinstance(resolved, list) and resolved:
                pages_with_annotations.append((index, resolved))
                expected_count += len(resolved)

        if expected_count == 0:
            return 0

        writer = PdfWriter(clone_from=output_reader)
        for index, annotations in pages_with_annotations:
            writer.pages[index][NameObject("/Annots")] = annotations.clone(writer)

        original_mode = output.stat().st_mode & 0o777
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}.", suffix=".annotations.pdf", dir=output.parent
        )
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)
        try:
            writer.write(str(temporary_path))
            restored_count = annotation_count(temporary_path)
            if restored_count != expected_count:
                raise RuntimeError(
                    f"restored {restored_count} of {expected_count} annotations"
                )
            temporary_path.replace(output)
            output.chmod(original_mode)
        finally:
            temporary_path.unlink(missing_ok=True)
        return expected_count
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"failed to restore PDF annotations: {exc}") from exc


def verify_mono_output(
    source_texts: list[str],
    source_sizes: list[tuple[float, float]],
    output: Path,
    reference_start: int | None,
    translated_pages: set[int] | None = None,
) -> str | None:
    try:
        output_texts, output_sizes = extract_page_texts(output)
    except RuntimeError as exc:
        return str(exc)
    if len(output_texts) != len(source_texts):
        return f"page count changed from {len(source_texts)} to {len(output_texts)}"
    if source_sizes and output_sizes:
        for page_number, (source_size, output_size) in enumerate(
            zip(source_sizes, output_sizes), 1
        ):
            if any(abs(a - b) > 0.1 for a, b in zip(source_size, output_size)):
                return (
                    f"page {page_number} size changed from {source_size} "
                    f"to {output_size}"
                )
    if reference_start:
        for index in range(reference_start - 1, len(source_texts)):
            if normalized_text(source_texts[index]) != normalized_text(output_texts[index]):
                return (
                    f"page {index + 1} changed even though references and later "
                    "content should remain untranslated"
                )
    markup = re.compile(r"</?\s*(style|样式)\b[^>]*>", re.IGNORECASE)
    pages_to_scan = translated_pages or set(range(1, len(output_texts) + 1))
    for page_number in sorted(pages_to_scan):
        text = output_texts[page_number - 1]
        match = markup.search(text)
        if match:
            return (
                f"page {page_number} contains leaked translation markup: "
                f"{match.group(0)!r}"
            )
    return None


def redact(tokens: list[str]) -> str:
    redacted = []
    hide_next = False
    for token in tokens:
        if hide_next:
            redacted.append("<redacted>")
            hide_next = False
        else:
            redacted.append(token)
            hide_next = token.lower().endswith(("api-key", "auth-key", "secret-key"))
    return " ".join(subprocess.list2cmdline([token]) for token in redacted)


def main() -> int:
    args = parser().parse_args()
    try:
        runner = find_runner(args.runner, not args.no_auto_install)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        completed = subprocess.run(runner + ["--version"], check=False)
        return completed.returncode

    if args.input_pdf is None:
        print("Error: input_pdf is required unless --check is used.", file=sys.stderr)
        return 2

    source = args.input_pdf.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pdf":
        print(f"Error: input is not an existing PDF: {source}", file=sys.stderr)
        return 2
    integrity_error = pdf_integrity_error(source)
    if integrity_error:
        print(f"Error: invalid PDF: {integrity_error}: {source}", file=sys.stderr)
        return 2

    try:
        source_texts, source_sizes = extract_page_texts(source)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    reference_start = None
    effective_pages = args.pages
    if not args.translate_references:
        reference_start = find_reference_start(source_texts)
        if reference_start:
            if reference_start == 1:
                print("Error: references begin on page 1; no content remains to translate.", file=sys.stderr)
                return 2
            if args.only_include_translated_page:
                print(
                    "Error: --only-include-translated-page would remove the preserved "
                    "references tail.",
                    file=sys.stderr,
                )
                return 2
            if effective_pages:
                try:
                    chosen = selected_pages(effective_pages, len(source_texts))
                except ValueError as exc:
                    print(f"Error: {exc}", file=sys.stderr)
                    return 2
                if any(page >= reference_start for page in chosen):
                    print(
                        f"Error: --pages includes page {reference_start} or later, but "
                        "references must remain untranslated.",
                        file=sys.stderr,
                    )
                    return 2
            else:
                effective_pages = f"1-{reference_start - 1}"
            print(
                f"References detected on page {reference_start}; translating "
                f"{effective_pages} and preserving page {reference_start} onward."
            )
        else:
            print("No references heading detected; translating the requested document range.")

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else source.parent / f"{source.stem}_translated"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    before = snapshot(output_dir)
    try:
        translated_pages = (
            selected_pages(effective_pages, len(source_texts))
            if effective_pages
            else set(range(1, len(source_texts) + 1))
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    command = runner + [
        str(source),
        "--lang-in",
        args.source,
        "--lang-out",
        args.target,
        "--output",
        str(output_dir),
        f"--{args.engine}",
        "--watermark-output-mode",
        args.watermark_mode,
    ]
    if args.mode == "mono":
        command.append("--no-dual")
    elif args.mode == "dual":
        command.append("--no-mono")
    if effective_pages:
        command += ["--pages", effective_pages]
    if args.qps is not None:
        if args.qps < 1:
            print("Error: --qps must be at least 1.", file=sys.stderr)
            return 2
        command += ["--qps", str(args.qps)]
    if args.enhance_compatibility:
        command.append("--enhance-compatibility")
    elif args.engine == "siliconflowfree" and not args.preserve_rich_text:
        command.append("--disable-rich-text-translate")
    if args.auto_enable_ocr_workaround:
        command.append("--auto-enable-ocr-workaround")
    if args.alternating_dual:
        command.append("--use-alternating-pages-dual")
    if args.only_include_translated_page:
        command.append("--only-include-translated-page")
    if not args.auto_extract_glossary:
        command.append("--no-auto-extract-glossary")
    if args.engine == "siliconflowfree" and args.enable_json_mode:
        command.append("--siliconflow-free-enable-json-mode")
    command.extend(args.pdf2zh_arg)

    print(f"Output directory: {output_dir}")
    if args.dry_run:
        print(f"Command: {redact(command)}")
        return 0

    try:
        completed = subprocess.run(command, check=False)
    except KeyboardInterrupt:
        print("Translation cancelled.", file=sys.stderr)
        return 130
    if completed.returncode != 0:
        print(f"Error: pdf2zh-next exited with code {completed.returncode}.", file=sys.stderr)
        return completed.returncode or 1

    after = snapshot(output_dir)
    generated = [
        path
        for path, details in after.items()
        if path not in before or before[path] != details
    ]
    generated = sorted(path for path in generated if path != source and valid_pdf(path))
    if not generated:
        print("Error: translation finished but no new or updated PDF was found.", file=sys.stderr)
        return 3

    print("Generated PDFs:")
    for path in generated:
        label = "bilingual" if ".dual." in path.name else "translated"
        if ".mono." in path.name:
            try:
                restored_annotations = restore_annotations(source, path)
            except RuntimeError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 4
            verification_error = verify_mono_output(
                source_texts,
                source_sizes,
                path,
                reference_start,
                translated_pages,
            )
            if verification_error:
                print(f"Error: output verification failed: {verification_error}", file=sys.stderr)
                return 4
            if annotation_count(path) != restored_annotations:
                print("Error: annotation-count verification failed", file=sys.stderr)
                return 4
        print(f"- [{label}] {path}")
        if ".mono." in path.name:
            print(
                "  verified: page count, page sizes, reference tail, markup, "
                f"and {restored_annotations} annotations"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
