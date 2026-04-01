from pdf2markdown import read_pdf

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m pdf2markdown <pdf_path>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    md = read_pdf(pdf_path)
    print(md)
