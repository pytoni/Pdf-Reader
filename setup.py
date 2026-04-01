import os

from setuptools import find_packages, setup

setup(
    name="pdf2markdown",
    version="0.1.0",
    description="A robust PDF-to-Markdown extraction library supporting all PDF types (text, scanned, complex)",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/pdf2markdown",
    packages=find_packages(),
    install_requires=["PyPDF2", "pdfplumber", "pdf2image", "pytesseract"],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
)
