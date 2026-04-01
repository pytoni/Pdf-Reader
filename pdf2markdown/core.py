import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO, List, Optional, Sequence, Union

try:
    import PyPDF2
except ImportError:  # pragma: no cover - exercised in integration environments
    PyPDF2 = None

try:
    import pdfplumber
except ImportError:  # pragma: no cover - exercised in integration environments
    pdfplumber = None

try:
    import pytesseract
except ImportError:  # pragma: no cover - exercised in integration environments
    pytesseract = None

try:
    from pdf2image import convert_from_bytes, convert_from_path
except ImportError:  # pragma: no cover - exercised in integration environments
    convert_from_bytes = None
    convert_from_path = None

if TYPE_CHECKING:
    import pdfplumber as pdfplumber_module


LOGGER_NAME = "pdf2markdown"
MIN_TEXT_LENGTH = 50
MARKDOWN_TABLE_SEPARATOR = " | "
BULLET_MARKERS = ("-", "*", "+", "\u2022", "\u25e6", "\u2023", "\u2043", "\u2219")


@dataclass
class PageContent:
    page_number: int
    text: str = ""
    tables: Optional[List[List[List[str]]]] = None
    source: str = "unknown"

    def render(self) -> str:
        sections: List[str] = []
        if self.text.strip():
            sections.append(to_markdown_format(self.text))
        for table in self.tables or []:
            markdown_table = table_to_markdown(table)
            if markdown_table:
                sections.append(markdown_table)
        return "\n\n".join(section for section in sections if section.strip()).strip()


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def clean_text(text: str) -> str:
    """Normalize spacing and join soft-wrapped lines while keeping paragraphs."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    raw_lines = [line.rstrip() for line in text.split("\n")]

    normalized: List[str] = []
    buffer = ""
    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            if buffer:
                normalized.append(buffer.strip())
                buffer = ""
            if normalized and normalized[-1] != "":
                normalized.append("")
            continue

        if not buffer:
            buffer = line
            continue

        if _should_join_lines(buffer, line):
            buffer = f"{buffer.rstrip()} {line.lstrip()}"
        else:
            normalized.append(buffer.strip())
            buffer = line

    if buffer:
        normalized.append(buffer.strip())

    cleaned_lines = _collapse_duplicate_blanks(normalized)
    return "\n".join(cleaned_lines).strip()


def to_markdown_format(text: str) -> str:
    """Convert extracted text into Markdown-friendly structure."""
    if not text:
        return ""

    lines = clean_text(text).splitlines()
    markdown_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if markdown_lines and markdown_lines[-1] != "":
                markdown_lines.append("")
            continue

        bullet = _normalize_bullet(stripped)
        if bullet:
            markdown_lines.append(bullet)
            continue

        numbered = _normalize_numbered_item(stripped)
        if numbered:
            markdown_lines.append(numbered)
            continue

        if _looks_like_key_value(stripped):
            key, value = stripped.split(":", 1)
            markdown_lines.append(f"**{key.strip()}**: {value.strip()}")
            continue

        if _is_heading(stripped):
            markdown_lines.append(f"## {stripped.title() if stripped.isupper() else stripped}")
            continue

        markdown_lines.append(stripped)

    return "\n".join(_collapse_duplicate_blanks(markdown_lines)).strip()


def table_to_markdown(table: Sequence[Sequence[object]]) -> str:
    """Convert a row/column table into a Markdown table."""
    sanitized_rows: List[List[str]] = []
    for row in table:
        if not row:
            continue
        sanitized = [clean_cell(cell) for cell in row]
        if any(cell for cell in sanitized):
            sanitized_rows.append(sanitized)

    if not sanitized_rows:
        return ""

    width = max(len(row) for row in sanitized_rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in sanitized_rows]
    header = normalized_rows[0]
    separator = ["---"] * width
    body = normalized_rows[1:] or [[""] * width]

    lines = [
        f"| {MARKDOWN_TABLE_SEPARATOR.join(header)} |",
        f"| {MARKDOWN_TABLE_SEPARATOR.join(separator)} |",
    ]
    lines.extend(f"| {MARKDOWN_TABLE_SEPARATOR.join(row)} |" for row in body)
    return "\n".join(lines)


def clean_cell(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def extract_text_with_pdfplumber(pdf_bytes: bytes) -> str:
    """Backward-compatible helper that returns plain extracted text."""
    pages = extract_pages_with_pdfplumber(pdf_bytes)
    return "\n\n".join(page.text.strip() for page in pages if page.text.strip()).strip()


def extract_pages_with_pdfplumber(pdf_bytes: bytes) -> List[PageContent]:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed.")
    pages: List[PageContent] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True, x_tolerance=2, y_tolerance=3) or ""
            if not text.strip():
                text = page.extract_text(x_tolerance=1.5, y_tolerance=1.5) or ""
            tables = _extract_page_tables(page)
            pages.append(PageContent(page_number=index, text=text, tables=tables, source="pdfplumber"))
    return pages


def extract_pages_with_pypdf2(pdf_bytes: bytes, max_workers: int = 4) -> List[str]:
    if PyPDF2 is None:
        raise RuntimeError("PyPDF2 is not installed.")
    reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))

    def extract(page: PyPDF2.PageObject) -> str:
        try:
            return page.extract_text() or ""
        except Exception:
            return ""

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(extract, reader.pages))


def read_pdf(
    pdf_input: Union[str, BytesIO, BinaryIO],
    use_ocr: bool = False,
    max_workers: int = 4,
    debug: bool = False,
    ocr_lang: str = "eng",
    ocr_dpi: int = 250,
) -> str:
    """
    Read a PDF from path, BytesIO, or a file-like object and return Markdown.

    The extractor is page-aware:
    - pdfplumber is used first for layout-aware text and tables.
    - PyPDF2 supplements pages with weak or empty results.
    - OCR is applied selectively for pages that still contain little text.
    """
    logger = setup_logging()
    pdf_path, pdf_bytes = _load_pdf_input(pdf_input)

    pages: List[PageContent]
    try:
        pages = extract_pages_with_pdfplumber(pdf_bytes)
    except Exception as exc:
        logger.warning("pdfplumber extraction failed, falling back to PyPDF2: %s", exc)
        pages = []

    pypdf2_pages: List[str] = []
    if not pages or any(_needs_text_fallback(page.text) for page in pages):
        try:
            pypdf2_pages = extract_pages_with_pypdf2(pdf_bytes, max_workers=max_workers)
        except Exception as exc:
            logger.warning("PyPDF2 extraction failed: %s", exc)

    total_pages = max(len(pages), len(pypdf2_pages))
    if not total_pages:
        raise ValueError("Unable to read any pages from the PDF.")

    if not pages:
        pages = [PageContent(page_number=i + 1, text="", tables=[], source="empty") for i in range(total_pages)]

    if len(pages) < total_pages:
        for index in range(len(pages) + 1, total_pages + 1):
            pages.append(PageContent(page_number=index, text="", tables=[], source="empty"))

    for index, fallback_text in enumerate(pypdf2_pages, start=1):
        page = pages[index - 1]
        if _is_better_text(candidate=fallback_text, current=page.text):
            page.text = fallback_text
            page.source = "pypdf2"

    if use_ocr or any(_page_needs_ocr(page) for page in pages):
        logger.info("Using OCR for pages with insufficient text.")
        _ensure_ocr_dependencies()
        for page in pages:
            if use_ocr or _page_needs_ocr(page):
                ocr_text = ocr_page(
                    page_number=page.page_number,
                    pdf_path=pdf_path,
                    pdf_bytes=pdf_bytes,
                    dpi=ocr_dpi,
                    lang=ocr_lang,
                )
                if _is_better_text(candidate=ocr_text, current=page.text):
                    page.text = ocr_text
                    page.source = "ocr"

    rendered_pages = []
    for page in pages:
        rendered = page.render()
        if rendered:
            rendered_pages.append(rendered)

    if not rendered_pages:
        raise ValueError("Unable to extract text from the PDF.")

    markdown = "\n\n---\n\n".join(rendered_pages).strip()
    if debug:
        print(markdown)
    return markdown


def ocr_page(page_number: int, pdf_path: Optional[str], pdf_bytes: bytes, dpi: int, lang: str) -> str:
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed.")
    image = _render_page_to_image(
        page_number=page_number,
        pdf_path=pdf_path,
        pdf_bytes=pdf_bytes,
        dpi=dpi,
    )
    text = pytesseract.image_to_string(image, lang=lang, config="--oem 3 --psm 6")
    return clean_text(text)


def _render_page_to_image(page_number: int, pdf_path: Optional[str], pdf_bytes: bytes, dpi: int):
    if convert_from_bytes is None or convert_from_path is None:
        raise RuntimeError("pdf2image is not installed.")
    if pdf_path:
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page_number,
            last_page=page_number,
            fmt="png",
            thread_count=1,
        )
    else:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            first_page=page_number,
            last_page=page_number,
            fmt="png",
            thread_count=1,
        )
    if not images:
        return None
    return images[0]


def _extract_page_tables(page: "pdfplumber_module.page.Page") -> List[List[List[str]]]:
    extracted_tables = page.extract_tables() or []
    tables: List[List[List[str]]] = []
    for table in extracted_tables:
        cleaned_rows = []
        for row in table or []:
            if row is None:
                continue
            cleaned_row = [clean_cell(cell) for cell in row]
            if any(cleaned_row):
                cleaned_rows.append(cleaned_row)
        if cleaned_rows:
            tables.append(cleaned_rows)
    return tables


def _load_pdf_input(pdf_input: Union[str, BytesIO, BinaryIO]) -> tuple[Optional[str], bytes]:
    if isinstance(pdf_input, str):
        if not os.path.exists(pdf_input):
            raise FileNotFoundError(f"File '{pdf_input}' not found.")
        with open(pdf_input, "rb") as file:
            return pdf_input, file.read()

    if isinstance(pdf_input, BytesIO):
        pdf_input.seek(0)
        return None, pdf_input.read()

    if hasattr(pdf_input, "read"):
        data = pdf_input.read()
        if not isinstance(data, bytes):
            raise ValueError("File-like PDF inputs must return bytes.")
        return None, data

    raise ValueError("Invalid PDF input type. Expected a path, BytesIO, or binary file object.")


def _ensure_ocr_dependencies() -> None:
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed. Please install it to process scanned PDFs.")
    if convert_from_bytes is None or convert_from_path is None:
        raise RuntimeError("pdf2image is not installed. Please install it to process scanned PDFs.")
    tesseract_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    if tesseract_cmd and os.path.exists(tesseract_cmd):
        return
    if shutil.which("tesseract"):
        return
    raise RuntimeError("Tesseract OCR not found. Please install it to process scanned PDFs.")


def _needs_text_fallback(text: str) -> bool:
    normalized = clean_text(text)
    return len(normalized) < 20


def _needs_ocr(text: str) -> bool:
    normalized = clean_text(text)
    return len(normalized) < MIN_TEXT_LENGTH or _text_looks_corrupted(normalized)


def _page_needs_ocr(page: PageContent) -> bool:
    if page.tables and not _text_looks_corrupted(clean_text(page.text)):
        return False
    return _needs_ocr(page.text)


def _text_looks_corrupted(text: str) -> bool:
    if not text:
        return True
    bad_glyphs = len(re.findall(r"[\uFFFD\u0000-\u001F]", text))
    return bad_glyphs > max(5, len(text) // 20)


def _is_better_text(candidate: str, current: str) -> bool:
    cleaned_candidate = clean_text(candidate)
    cleaned_current = clean_text(current)
    if not cleaned_candidate:
        return False
    if not cleaned_current:
        return True
    if _text_looks_corrupted(cleaned_current) and not _text_looks_corrupted(cleaned_candidate):
        return True
    return len(cleaned_candidate) > len(cleaned_current) * 1.15


def _should_join_lines(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if _starts_block(current):
        return False
    if previous.endswith((".", ":", ";", "?", "!", "|")):
        return False
    if previous.endswith("-") and previous[:-1]:
        return False
    return True


def _starts_block(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _normalize_bullet(stripped) or _normalize_numbered_item(stripped):
        return True
    if _is_heading(stripped):
        return True
    if stripped.startswith("|"):
        return True
    return False


def _normalize_bullet(line: str) -> Optional[str]:
    bullet_pattern = re.compile(rf"^\s*([{''.join(re.escape(marker) for marker in BULLET_MARKERS)}])\s+(.*)$")
    match = bullet_pattern.match(line)
    if not match:
        return None
    return f"- {match.group(2).strip()}"


def _normalize_numbered_item(line: str) -> Optional[str]:
    match = re.match(r"^\s*(\d+)[\.\)]\s+(.*)$", line)
    if not match:
        return None
    return f"{match.group(1)}. {match.group(2).strip()}"


def _is_heading(line: str) -> bool:
    if len(line) < 4 or len(line) > 80:
        return False
    if line.endswith((".", ";", ":", ",")):
        return False
    if _normalize_bullet(line) or _normalize_numbered_item(line):
        return False
    if line.isupper() and re.search(r"[A-Z]", line):
        return True
    words = line.split()
    if len(words) <= 10 and sum(word[:1].isupper() for word in words) >= max(1, len(words) - 1):
        return True
    return False


def _looks_like_key_value(line: str) -> bool:
    if line.count(":") != 1:
        return False
    key, value = line.split(":", 1)
    if not key or not value.strip():
        return False
    return len(key.split()) <= 4 and len(key) <= 30


def _collapse_duplicate_blanks(lines: Sequence[str]) -> List[str]:
    collapsed: List[str] = []
    for line in lines:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)
    if collapsed and collapsed[0] == "":
        collapsed = collapsed[1:]
    if collapsed and collapsed[-1] == "":
        collapsed = collapsed[:-1]
    return collapsed
