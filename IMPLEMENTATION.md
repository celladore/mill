# Mill Python Compatibility Implementation

This document describes Mill's compatible `xtotext` Python distribution and
`xtox` import namespace, focusing on the Markdown -> LaTeX -> PDF pipeline.

## Core Components

### 1. Markdown to LaTeX Conversion (`markdown_to_latex.py`)

The Markdown to LaTeX converter handles:

- Headers (h1-h5)
- Lists (ordered and unordered)
- Code blocks with syntax highlighting
- Images with captions
- Tables
- Blockquotes
- Inline formatting (bold, italic, code)
- Links

The converter generates a complete LaTeX document with appropriate preamble and structure.

### 2. LaTeX to PDF Conversion (`latex_to_pdf.py`)

The LaTeX to PDF converter:

- Checks for pdflatex installation
- Validates LaTeX document structure
- Fixes common structural issues
- Runs pdflatex to generate PDF
- Provides detailed error reporting

### 3. Document Converter (`document_converter.py`)

The main orchestrator class that:

- Manages the conversion pipeline
- Handles file paths and output directories
- Processes images and other assets
- Applies refinements based on the specified level
- Returns detailed results of the conversion

## Workflow

The `process_markdown_to_pdf` workflow function in `workflows/md_to_pdf.py` provides a high-level interface for the conversion process:

1. Read the Markdown file
2. Process and copy images
3. Convert Markdown to LaTeX
4. Apply LaTeX refinements based on the refinement level
5. Generate PDF from LaTeX
6. Return paths to all generated files

## Command Line Interface

The CLI in `cli/main.py` provides a user-friendly interface for the conversion process:

```
xtotext input.md -o output_dir -r 2
```

Options:
- `-o, --output`: Output directory
- `-r, --refinement`: Refinement level (0-3)
- `--format`: Output format (pdf or latex)
- `--skip-pdf`: Skip PDF generation
- `-v, --verbose`: Enable verbose output

## Testing

Tests are provided in the `tests` directory:

- Unit tests for individual components
- Integration tests for the full pipeline
- Tests that skip PDF generation if pdflatex is not installed

## Examples

Example scripts in the `examples` directory demonstrate:

- Using the DocumentConverter class
- Using the workflow function
- Command-line usage

## Refinement Levels

The package supports different levels of LaTeX refinement:

- Level 0: No refinement
- Level 1: Basic structure fixes
- Level 2: Structure fixes with backup
- Level 3: Reserved for future advanced refinements

## Future Enhancements

Potential future enhancements include:

- Support for more Markdown features
- Advanced LaTeX customization
- PDF metadata management
- Custom LaTeX templates
- Integration with AI services for content enhancement
