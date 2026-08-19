"""
Utility functions for LaTeX processing and error handling.
"""
from typing import List, Tuple

def parse_latex_errors(log_content: str) -> Tuple[List[str], List[str]]:
    """Parse LaTeX log file to extract errors and warnings"""
    errors = []
    warnings = []

    lines = log_content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('!') and 'Error' in line:
            error_msg = line
            # Try to get the next few lines for more context
            for j in range(i + 1, min(i + 3, len(lines))):
                if lines[j].strip() and not lines[j].startswith('l.'):
                    error_msg += " " + lines[j].strip()
                if lines[j].startswith('l.'):
                    error_msg += " " + lines[j].strip()
                    break
            errors.append(error_msg)
        elif 'Warning' in line and not line.startswith('('):
            warnings.append(line.strip())

    return errors, warnings

def auto_fix_latex(content: str) -> Tuple[str, bool]:
    """Apply basic auto-fixes to LaTeX content"""
    original_content = content
    fixed = False

    # Remove BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]
        fixed = True

    # Check for \documentclass
    if '\\documentclass' not in content:
        content = '\\documentclass{article}\n' + content
        fixed = True

    # Check for \begin{document}
    if '\\begin{document}' not in content:
        # Find where to insert \begin{document}
        lines = content.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('\\documentclass'):
                insert_pos = i + 1
                break
        lines.insert(insert_pos, '\\begin{document}')
        content = '\n'.join(lines)
        fixed = True

    # Check for \end{document}
    if '\\end{document}' not in content:
        content = content + '\n\\end{document}'
        fixed = True

    return content, fixed
