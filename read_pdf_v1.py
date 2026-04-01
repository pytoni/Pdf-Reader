#read_pdf.py
import logging
import os
import re
import shutil
import tempfile
from io import BytesIO
from typing import Union
from concurrent.futures import ThreadPoolExecutor

import PyPDF2
import pdfplumber
from pdf2image import convert_from_bytes, convert_from_path
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    return logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Normalize spacing and line breaks while preserving layout."""
    if not text:
        return ""
    text = text.replace('\r\n', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def to_markdown_format(text: str) -> str:
    """Convert structured text to Markdown-style layout."""
    if not text:
        return ""

    lines = text.splitlines()
    md_lines = []
    for line in lines:
        line = line.rstrip()
        if not line.strip():
            md_lines.append("")
            continue

        # Header detection
        if re.match(r'^[A-Z][A-Z\s]{4,}$', line.strip()):
            md_lines.append(f"## {line.strip().title()}")

        # Bullet points
        elif re.match(r'^\s*[•*-]\s+', line):
            md_lines.append(f"- {line.strip()[2:].strip()}")

        # Table-like: multiple spaces
        elif re.search(r'\s{2,}', line):
            md_lines.append(f"`{line}`")

        else:
            md_lines.append(line)
    return "\n".join(md_lines)


def extract_text_with_pdfplumber(pdf_bytes: bytes) -> str:
    """Extract text using pdfplumber for better layout accuracy."""
    text = ""
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=1.5, y_tolerance=1.5)
            if page_text:
                text += page_text + "\n\n"
    return text


def read_pdf(pdf_input: Union[str, BytesIO], use_ocr: bool = False, max_workers: int = 4, debug: bool = False) -> str:
    logger = setup_logging()
    pdf_bytes = None
    temp_dir = None

    try:
        # Handle input type
        if isinstance(pdf_input, str):
            if not os.path.exists(pdf_input):
                raise FileNotFoundError(f"File '{pdf_input}' not found.")
            with open(pdf_input, "rb") as file:
                pdf_bytes = file.read()
        elif isinstance(pdf_input, BytesIO):
            pdf_input.seek(0)
            pdf_bytes = pdf_input.read()
        else:
            raise ValueError("Invalid PDF input type.")

        # Try structured extraction with pdfplumber
        text = extract_text_with_pdfplumber(pdf_bytes)

        # Fallback to PyPDF2 if pdfplumber fails
        if not text.strip():
            reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                page_texts = executor.map(lambda p: p.extract_text() or "", reader.pages)
                text = "\n\n".join(page_texts)

        # OCR fallback if no valid text or use_ocr is True
        if use_ocr or not text.strip() or len(text.strip()) < 50:
            logger.info("Using OCR for text extraction.")
            if not shutil.which("tesseract"):
                raise RuntimeError("Tesseract OCR not found. Please install it.")

            temp_dir = tempfile.mkdtemp()
            ocr_text = ""

            # Use convert_from_path for file paths, convert_from_bytes for BytesIO
            if isinstance(pdf_input, str):
                images = convert_from_path(pdf_input, output_folder=temp_dir, fmt="png", thread_count=max_workers)
            else:
                images = convert_from_bytes(pdf_bytes, output_folder=temp_dir, fmt="png", thread_count=max_workers)

            # Extract text from each image
            for i, img in enumerate(images):
                ocr_result = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
                if ocr_result.strip():
                    ocr_text += f"Page {i+1}:\n{ocr_result}\n\n"

            if not ocr_text.strip():
                raise ValueError("OCR failed to extract any text.")
            text = ocr_text

        cleaned = clean_text(text)
        if debug:
            print("---- RAW TEXT ----")
            print(cleaned)
        return to_markdown_format(cleaned)

    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)



# import logging
# import os
# import re
# import shutil
# import tempfile
# from io import BytesIO
# from typing import Union
# from concurrent.futures import ThreadPoolExecutor

# import PyPDF2
# import pdfplumber
# from pdf2image import convert_from_bytes
# import pytesseract


# def setup_logging():
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
#     return logging.getLogger(__name__)


# def clean_text(text: str) -> str:
#     """Normalize spacing and line breaks while preserving layout."""
#     if not text:
#         return ""
#     text = text.replace('\r\n', '\n')
#     text = re.sub(r'[ \t]+', ' ', text)
#     text = re.sub(r'\n{3,}', '\n\n', text)
#     return text.strip()


# def to_markdown_format(text: str) -> str:
#     """Convert structured text to Markdown-style layout."""
#     if not text:
#         return ""

#     lines = text.splitlines()
#     md_lines = []
#     for line in lines:
#         line = line.rstrip()
#         if not line.strip():
#             md_lines.append("")
#             continue

#         # Header detection
#         if re.match(r'^[A-Z][A-Z\s]{4,}$', line.strip()):
#             md_lines.append(f"## {line.strip().title()}")

#         # Bullet points
#         elif re.match(r'^\s*[•*-]\s+', line):
#             md_lines.append(f"- {line.strip()[2:].strip()}")

#         # Table-like: multiple spaces
#         elif re.search(r'\s{2,}', line):
#             md_lines.append(f"`{line}`")

#         else:
#             md_lines.append(line)
#     return "\n".join(md_lines)


# def extract_text_with_pdfplumber(pdf_bytes: bytes) -> str:
#     """Extract text using pdfplumber for better layout accuracy."""
#     text = ""
#     with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
#         for page in pdf.pages:
#             page_text = page.extract_text(x_tolerance=1.5, y_tolerance=1.5)
#             if page_text:
#                 text += page_text + "\n\n"
#     return text


# def read_pdf(pdf_input: Union[str, BytesIO], use_ocr: bool = False, max_workers: int = 4, debug: bool = False) -> str:
#     logger = setup_logging()
#     pdf_bytes = None
#     temp_dir = None

#     try:
#         if isinstance(pdf_input, str):
#             if not os.path.exists(pdf_input):
#                 raise FileNotFoundError(f"File '{pdf_input}' not found.")
#             with open(pdf_input, "rb") as file:
#                 pdf_bytes = file.read()
#         elif isinstance(pdf_input, BytesIO):
#             pdf_input.seek(0)
#             pdf_bytes = pdf_input.read()
#         else:
#             raise ValueError("Invalid PDF input type.")

#         # Try structured extraction with pdfplumber
#         text = extract_text_with_pdfplumber(pdf_bytes)

#         # Fallback to PyPDF2 if plumber fails
#         if not text.strip():
#             reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
#             with ThreadPoolExecutor(max_workers=max_workers) as executor:
#                 page_texts = executor.map(lambda p: p.extract_text() or "", reader.pages)
#                 text = "\n\n".join(page_texts)

#         # OCR fallback if no valid text
#         if use_ocr or not text.strip() or len(text.strip()) < 50:
#             logger.info("Using OCR for text extraction.")
#             if not shutil.which("tesseract"):
#                 raise RuntimeError("Tesseract OCR not found. Please install it.")

#             temp_dir = tempfile.mkdtemp()
#             images = convert_from_bytes(pdf_bytes, output_folder=temp_dir, fmt="png", thread_count=max_workers)

#             ocr_text = ""
#             for img in images:
#                 ocr_result = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
#                 ocr_text += ocr_result + "\n\n"

#             if not ocr_text.strip():
#                 raise ValueError("OCR failed to extract any text.")
#             text = ocr_text

#         cleaned = clean_text(text)
#         if debug:
#             print("---- RAW TEXT ----")
#             print(cleaned)
#         return to_markdown_format(cleaned)

#     finally:
#         if temp_dir and os.path.exists(temp_dir):
#             shutil.rmtree(temp_dir)



