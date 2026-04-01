# pdf2markdown

A robust Python library to extract text from any PDF (text, scanned, or complex) and return it in Markdown format.

## Features
- Handles text-based, scanned, and complex PDFs
- Uses pdfplumber, PyPDF2, and pytesseract (OCR) for best results
- Returns clean Markdown-formatted output
- Simple API: `read_pdf(path_or_bytesio)`

## Installation
```
pip install pdf2markdown
```

## Usage
```python
from pdf2markdown import read_pdf

# Read from file path
markdown_text = read_pdf("example.pdf")

# Read from BytesIO
# from io import BytesIO
# with open("example.pdf", "rb") as f:
#     markdown_text = read_pdf(BytesIO(f.read()))

print(markdown_text)
```

## Requirements
- Python 3.7+
- Tesseract OCR (for scanned PDFs): https://github.com/tesseract-ocr/tesseract

## License
MIT
