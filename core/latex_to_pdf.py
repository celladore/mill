import subprocess
import sys
import os
import re


def check_pdflatex_installed():
    """Check if pdflatex is installed and available."""
    try:
        result = subprocess.run(
            ["pdflatex", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_latex_structure(tex_path):
    """
    Check if the LaTeX file has the required structure.
    Returns a tuple: (has_documentclass, has_begin_document, has_end_document)
    """
    with open(tex_path, "r", encoding="utf-8") as file:
        content = file.read()

    has_documentclass = bool(re.search(r"\\documentclass(\[.*?\])?\{.*?\}", content))
    has_begin_document = "\\begin{document}" in content
    has_end_document = "\\end{document}" in content

    return has_documentclass, has_begin_document, has_end_document


def fix_latex_structure(tex_path, backup=True):
    """
    Attempt to fix common LaTeX structure issues by adding missing elements.
    Creates a backup of the original file if backup=True.
    """
    if backup:
        backup_path = f"{tex_path}.bak"
        os.rename(tex_path, backup_path)
        with open(backup_path, "r", encoding="utf-8") as file:
            content = file.read()
    else:
        with open(tex_path, "r", encoding="utf-8") as file:
            content = file.read()

    has_documentclass, has_begin_document, has_end_document = check_latex_structure(
        backup_path if backup else tex_path
    )

    # Add missing structure
    if not has_documentclass:
        content = "\\documentclass{article}\n\n" + content

    if not has_begin_document:
        # Add begin{document} after the preamble (after last \usepackage or \documentclass)
        preamble_end = max(
            content.rfind("\\documentclass"), content.rfind("\\usepackage")
        )
        if preamble_end > -1:
            content = content[:preamble_end] + content[preamble_end:].replace(
                "\n", "\n\n\\begin{document}\n", 1
            )
        else:
            content = "\\begin{document}\n" + content

    if not has_end_document:
        content += "\n\\end{document}"

    # Write the fixed content
    with open(tex_path, "w", encoding="utf-8") as file:
        file.write(content)

    print(f"Fixed LaTeX structure in {tex_path}")
    if backup:
        print(f"Original file backed up to {backup_path}")
    return True


def latex_to_pdf(tex_path, auto_fix=False):
    """
    Convert LaTeX file to PDF using pdflatex.
    If auto_fix is True, attempts to fix common structure issues.
    """
    tex_path = os.path.abspath(tex_path)
    if not os.path.isfile(tex_path):
        print(f"File not found: {tex_path}")
        return False

    # Check LaTeX structure
    has_documentclass, has_begin_document, has_end_document = check_latex_structure(
        tex_path
    )
    if not all([has_documentclass, has_begin_document, has_end_document]):
        print("LaTeX file appears to have structural issues:")
        if not has_documentclass:
            print("- Missing \\documentclass declaration")
        if not has_begin_document:
            print("- Missing \\begin{document}")
        if not has_end_document:
            print("- Missing \\end{document}")

        if auto_fix:
            print("Attempting to fix structure issues...")
            fix_latex_structure(tex_path)
        else:
            print("Run with --auto-fix option to attempt automatic repair")
            return False

    # Run pdflatex twice for references and cross-references
    tex_dir = os.path.dirname(tex_path)
    tex_filename = os.path.basename(tex_path)
    for i in range(2):
        print(f"Running pdflatex (pass {i+1}/2)...")
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_filename],
            cwd=tex_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode != 0:
            print("Error during pdflatex run:")

            # Extract and display specific LaTeX errors
            output = result.stdout
            errors = re.findall(r"! (.*?)\.[\r\n]l\.(\d+)", output)

            if errors:
                print("\nLaTeX Errors Found:")
                for err, line in errors:
                    print(f"Line {line}: {err}")
                print("\nFull output:")

            print(output)
            print(result.stderr)
            return False

    pdf_path = f"{os.path.splitext(tex_path)[0]}.pdf"
    if os.path.isfile(pdf_path):
        print(f"PDF generated successfully: {pdf_path}")
        return True
    else:
        print(f"PDF generation failed: {pdf_path} not found")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python latex_to_pdf.py <file.tex> [--auto-fix]")
    else:
        tex_file = sys.argv[1]
        auto_fix = "--auto-fix" in sys.argv
        latex_to_pdf(tex_file, auto_fix)
