import argparse

from pdf2markdown import read_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract PDF content and return Markdown.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--ocr", action="store_true", help="Force OCR on every page")
    parser.add_argument("--ocr-lang", default="eng", help="OCR language passed to Tesseract")
    parser.add_argument("--ocr-dpi", type=int, default=250, help="DPI used when rendering OCR images")
    args = parser.parse_args()

    markdown = read_pdf(
        args.pdf_path,
        use_ocr=args.ocr,
        ocr_lang=args.ocr_lang,
        ocr_dpi=args.ocr_dpi,
    )
    print(markdown)


if __name__ == "__main__":
    main()
