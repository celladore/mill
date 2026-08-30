"""
Test the Markdown to PDF conversion workflow.
"""

import os
import pytest
from pathlib import Path

from xtox.core import DocumentConverter
from xtox.workflows import process_markdown_to_pdf


def test_document_converter_init():
    """Test DocumentConverter initialization."""
    converter = DocumentConverter()
    assert converter.output_dir is None
    
    converter = DocumentConverter(output_dir="./output")
    assert converter.output_dir == Path("./output")


def test_markdown_to_latex_conversion(tmp_path):
    """Test converting Markdown to LaTeX."""
    # Create a test markdown file
    md_content = """# Test Document
    
This is a test document with some **bold** and *italic* text.

## Section 1

- Item 1
- Item 2
- Item 3

### Subsection

Here's some code:

```python
def hello_world():
    print("Hello, world!")
```

"""
    md_file = tmp_path / "test.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # Convert to LaTeX
    from xtox.core import convert_markdown_to_latex
    latex_file = tmp_path / "test.tex"
    latex_content = convert_markdown_to_latex(md_content, str(latex_file))
    
    # Check that the LaTeX file was created
    assert os.path.exists(latex_file)
    
    # Check that the LaTeX content contains expected elements
    assert "\\section{Test Document}" in latex_content
    assert "\\subsection{Section 1}" in latex_content
    assert "\\begin{itemize}" in latex_content
    assert "\\begin{lstlisting}[language=python]" in latex_content
    assert "\\section{Test Document}\n\n" in latex_content
    assert "\\begin{itemize}\n\\item Item 1\n" in latex_content


@pytest.mark.skipif(
    os.system("pdflatex --version > nul 2>&1") != 0,
    reason="pdflatex not installed"
)
def test_full_conversion_workflow(tmp_path):
    """Test the full Markdown to PDF conversion workflow."""
    # Create a test markdown file
    md_content = """# Test Document
    
This is a test document for the conversion workflow.

## Section 1

- Item 1
- Item 2
- Item 3
"""
    md_file = tmp_path / "test.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # Run the workflow
    result = process_markdown_to_pdf(md_file, output_dir=str(tmp_path))
    
    # Check that the output files were created
    assert os.path.exists(result["latex_path"])
    assert os.path.exists(result["pdf_path"])
