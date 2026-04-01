# pdf2markdown

`pdf2markdown` is a Python library for extracting content from PDFs and returning Markdown that is easier to read, search, and reuse.

It handles:
- Text PDFs
- Mixed-layout PDFs
- PDFs with tables
- Scanned PDFs through OCR fallback

## Features

- Page-aware extraction with staged fallbacks
- `pdfplumber` for layout-aware text and tables
- `PyPDF2` fallback for weak or empty text pages
- Selective OCR using `pytesseract` and `pdf2image`
- Markdown output with headings, lists, paragraphs, tables, and page separators
- Supports file paths, `BytesIO`, and binary file-like objects

## Installation

```bash
pip install git+https://github.com/pytoni/Pdf-Reader.git
```

For scanned PDFs, install OCR dependencies too:

- Tesseract OCR: https://github.com/tesseract-ocr/tesseract
- Poppler: required by `pdf2image` on many systems

## Quick Start

```python
from pdf2markdown import read_pdf

markdown = read_pdf("example.pdf")
print(markdown)
```

## Usage

Read from a file path:

```python
from pdf2markdown import read_pdf

markdown = read_pdf("example.pdf")
```

Read from `BytesIO`:

```python
from io import BytesIO

from pdf2markdown import read_pdf

with open("example.pdf", "rb") as file:
    markdown = read_pdf(BytesIO(file.read()))
```

Force OCR for every page:

```python
markdown = read_pdf("scanned.pdf", use_ocr=True)
```

Change OCR language or image quality:

```python
markdown = read_pdf("document.pdf", ocr_lang="eng", ocr_dpi=300)
```

Use the CLI:

```bash
python -m pdf2markdown example.pdf
```

## Output Shape

The returned Markdown is normalized to be practical rather than pixel-perfect:

- Short title-like lines become Markdown headings
- Bullets and numbered lists are normalized
- Tables are emitted as Markdown tables when detected
- Pages are separated by `---`

## API

```python
read_pdf(
    pdf_input,
    use_ocr=False,
    max_workers=4,
    debug=False,
    ocr_lang="eng",
    ocr_dpi=250,
)
```

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

Build a source distribution:

```bash
python -m build
```

Upload to PyPI:

```bash
python -m twine upload dist/*
```

## License

MIT. See [LICENSE](LICENSE).
