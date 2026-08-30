import argparse
import sys
import os
from pathlib import Path
from typing import Optional

from xtox.core import DocumentConverter
from xtox.core.latex_to_pdf import check_pdflatex_installed


def validate_file(file_path: str) -> Path:
    """
    Validate that the file exists and return a Path object.
    """
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {path}")
        sys.exit(1)
    if not path.is_file():
        print(f"Error: Not a file: {path}")
        sys.exit(1)
    return path


def main():
    """
    Main entry point for the CLI.
    """
    parser = argparse.ArgumentParser(
        description="Mill local conversion compatibility CLI (xtotext executable)"
    )
    parser.add_argument(
        "input_files", 
        nargs='+',
        help="Input file(s) to convert"
    )
    parser.add_argument(
        "-o", "--output", 
        help="Output directory (default: same as input file)"
    )
    parser.add_argument(
        "-r", "--refinement", 
        type=int, 
        default=1, 
        choices=[0, 1, 2, 3],
        help="LaTeX refinement level (0-3, default: 1)"
    )
    parser.add_argument(
        "--format", 
        choices=["pdf", "latex", "docx", "html", "jpeg", "png", "webp"], 
        default="pdf",
        help="Output format (default: pdf)"
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip PDF generation (only create LaTeX)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--use-case",
        choices=["web", "print", "archive", "editing", "ai_processing"],
        help="Target use case for format selection"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process multiple files with intelligent format selection"
    )
    parser.add_argument(
        "--image-quality",
        choices=["high", "medium", "low", "web"],
        default="high",
        help="Image quality preset"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive mode - review and modify conversion settings"
    )
    
    args = parser.parse_args()
    
    # Validate input files
    input_paths = [validate_file(f) for f in args.input_files]
    
    # Check for pdflatex if we're generating PDFs
    if not args.skip_pdf and args.format == "pdf":
        if not check_pdflatex_installed():
            print("Error: pdflatex is not installed or not in the system path.")
            print("Please install a LaTeX distribution like TeX Live, MiKTeX, or MacTeX.")
            print("Alternatively, use --skip-pdf to generate only LaTeX output.")
            sys.exit(1)
    
    # Create output directory if specified
    output_dir: Optional[str] = None
    if args.output:
        output_dir = args.output
        os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Handle interactive processing
        if args.interactive:
            from xtox.core import InteractiveProcessor
            
            processor = InteractiveProcessor(output_dir)
            use_case = args.use_case or 'web'
            
            results = processor.process_with_user_input(input_paths, use_case)
            
            if results.get('status') == 'cancelled':
                print("Processing cancelled by user.")
            else:
                print(f"\n🎉 Interactive processing complete!")
            
            return
        
        # Handle batch processing
        elif args.batch or len(input_paths) > 1:
            from xtox.core import MultiDocumentProcessor
            
            processor = MultiDocumentProcessor(output_dir)
            
            # Determine user preferences
            user_prefs = {}
            if args.format != 'pdf':
                user_prefs['documents'] = args.format
            
            if args.verbose:
                print(f"Processing {len(input_paths)} files in batch mode")
                if args.use_case:
                    print(f"Use case: {args.use_case}")
            
            results = processor.process_documents(
                input_paths,
                target_use_case=args.use_case,
                user_preferences=user_prefs,
                output_dir=output_dir
            )
            
            print(f"\nBatch processing complete!")
            print(f"Documents processed: {len(results['documents'])}")
            print(f"Images processed: {len(results['images'])}")
            if results['errors']:
                print(f"Errors: {len(results['errors'])}")
                for error in results['errors']:
                    print(f"  - {error}")
            
            return
        
        # Single file processing
        converter = DocumentConverter(output_dir=output_dir)
        input_path = input_paths[0]
        
        # Handle image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp'}
        if input_path.suffix.lower() in image_extensions:
            from xtox.core import ImageConverter
            img_converter = ImageConverter()
            
            if args.format in ['jpeg', 'png', 'webp']:
                output_path = img_converter.convert_image(
                    input_path,
                    target_format=args.format,
                    quality=args.image_quality
                )
                print(f"Success! Image converted: {output_path}")
            else:
                print(f"Error: Format '{args.format}' not supported for images")
                print("Supported image formats: jpeg, png, webp")
            return
        
        if input_path.suffix.lower() == '.md':
            if args.verbose:
                print(f"Converting Markdown file: {input_path}")
                print(f"Refinement level: {args.refinement}")
                print(f"Output directory: {output_dir or input_path.parent}")
            
            if args.format == "docx":
                # Convert to DOCX
                docx_path = converter.markdown_to_docx(input_path, output_dir)
                print(f"Success! DOCX file generated: {docx_path}")
            elif args.format == "html":
                # Convert to HTML
                html_path = converter.markdown_to_html(input_path, output_dir)
                print(f"Success! HTML file generated: {html_path}")
            elif args.skip_pdf or args.format == "latex":
                # Only convert to LaTeX
                latex_path = output_dir / f"{input_path.stem}.tex" if output_dir else input_path.with_suffix('.tex')
                with open(input_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                from xtox.core import convert_markdown_to_latex
                convert_markdown_to_latex(markdown_content, str(latex_path))
                print(f"Success! LaTeX file generated: {latex_path}")
            else:
                # Convert to PDF
                result = converter.markdown_to_pdf(
                    input_path, 
                    output_dir, 
                    args.refinement
                )
                print(f"\nSuccess! Files generated:")
                print(f"  LaTeX: {result['latex_path']}")
                print(f"  PDF: {result['pdf_path']}")
                if result['images']:
                    print(f"  Images: {len(result['images'])} files copied")
        
        elif input_path.suffix.lower() == '.html':
            if args.verbose:
                print(f"Converting HTML file to Markdown: {input_path}")
            md_path = converter.html_to_markdown(input_path, output_dir)
            print(f"Success! Markdown file generated: {md_path}")
        
        elif input_path.suffix.lower() == '.tex':
            if args.skip_pdf or args.format == "latex":
                print(f"No conversion needed for LaTeX file: {input_path}")
            else:
                if args.verbose:
                    print(f"Converting LaTeX file to PDF: {input_path}")
                pdf_path = converter.latex_to_pdf(input_path, auto_fix=(args.refinement > 0))
                print(f"Success! PDF generated: {pdf_path}")
        
        else:
            print(f"Error: Unsupported file format: {input_path.suffix}")
            print("Supported formats: .md, .html, .tex, .jpg, .png, .webp, etc.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
