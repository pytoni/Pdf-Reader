from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from pdf2markdown.core import PageContent, read_pdf, table_to_markdown, to_markdown_format


class MarkdownFormattingTests(TestCase):
    def test_markdown_normalizes_headings_lists_and_key_values(self):
        text = """
        DOCUMENT TITLE

        • first item
        2) second item
        Author: Jane Doe

        This is a wrapped
        paragraph that should stay together.
        """

        markdown = to_markdown_format(text)

        self.assertIn("## Document Title", markdown)
        self.assertIn("- first item", markdown)
        self.assertIn("2. second item", markdown)
        self.assertIn("**Author**: Jane Doe", markdown)
        self.assertIn("This is a wrapped paragraph that should stay together.", markdown)

    def test_table_to_markdown_builds_header_separator(self):
        table = [
            ["Name", "Value"],
            ["Alpha", "1"],
        ]

        markdown = table_to_markdown(table)

        self.assertEqual(
            markdown,
            "| Name | Value |\n| --- | --- |\n| Alpha | 1 |",
        )


class ReadPdfFallbackTests(TestCase):
    @patch("pdf2markdown.core.extract_pages_with_pypdf2")
    @patch("pdf2markdown.core.extract_pages_with_pdfplumber")
    def test_read_pdf_uses_pypdf2_when_pdfplumber_page_is_sparse(self, plumber_mock, pypdf2_mock):
        plumber_mock.return_value = [PageContent(page_number=1, text="tiny", tables=[], source="pdfplumber")]
        pypdf2_mock.return_value = ["This page has enough extracted text to beat the sparse result."]

        markdown = read_pdf(BytesIO(b"%PDF-test"), use_ocr=False)

        self.assertIn("This page has enough extracted text", markdown)

    @patch("pdf2markdown.core._ensure_ocr_dependencies")
    @patch("pdf2markdown.core.ocr_page")
    @patch("pdf2markdown.core.extract_pages_with_pypdf2")
    @patch("pdf2markdown.core.extract_pages_with_pdfplumber")
    def test_read_pdf_uses_ocr_for_unreadable_pages(self, plumber_mock, pypdf2_mock, ocr_mock, ensure_ocr_mock):
        plumber_mock.return_value = [PageContent(page_number=1, text="", tables=[], source="pdfplumber")]
        pypdf2_mock.return_value = [""]
        ocr_mock.return_value = "Scanned page text recovered through OCR with enough detail to pass the threshold."

        markdown = read_pdf(BytesIO(b"%PDF-test"), use_ocr=False)

        ensure_ocr_mock.assert_called_once()
        ocr_mock.assert_called_once()
        self.assertIn("Scanned page text recovered through OCR", markdown)

    @patch("pdf2markdown.core.extract_pages_with_pypdf2")
    @patch("pdf2markdown.core.extract_pages_with_pdfplumber")
    def test_read_pdf_renders_tables_in_markdown(self, plumber_mock, pypdf2_mock):
        plumber_mock.return_value = [
            PageContent(
                page_number=1,
                text="Quarterly Results",
                tables=[[["Quarter", "Revenue"], ["Q1", "$10"]]],
                source="pdfplumber",
            )
        ]
        pypdf2_mock.return_value = []

        markdown = read_pdf(BytesIO(b"%PDF-test"), use_ocr=False)

        self.assertIn("## Quarterly Results", markdown)
        self.assertIn("| Quarter | Revenue |", markdown)
