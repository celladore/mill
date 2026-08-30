import re
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple

def convert_markdown_to_latex(markdown_content: str, output_path: Optional[str] = None, include_preamble: bool = True) -> str:
    """
    Convert Markdown content to LaTeX.
    
    Parameters:
    -----------
    markdown_content : str
        The Markdown content to convert
    output_path : str, optional
        Path to save the LaTeX output
    include_preamble : bool, default=True
        Whether to include a standard LaTeX preamble
        
    Returns:
    --------
    str
        The LaTeX content
    """
    # Initialize LaTeX content with a standard preamble if requested
    latex_content = ""
    if include_preamble:
        latex_content = """\\documentclass{article}
\\usepackage[utf8]{inputenc}
\\usepackage{graphicx}
\\usepackage{hyperref}
\\usepackage{amsmath}
\\usepackage{amssymb}
\\usepackage{listings}
\\usepackage{xcolor}
\\usepackage{booktabs}
\\usepackage{geometry}
\\usepackage{fancyhdr}
\\usepackage{titlesec}
\\usepackage{enumitem}

\\geometry{margin=1in}
\\definecolor{linkcolor}{RGB}{0,102,204}
\\hypersetup{colorlinks=true, linkcolor=linkcolor, urlcolor=linkcolor}

\\lstset{
  basicstyle=\\ttfamily\\small,
  breaklines=true,
  frame=single,
  numbers=left,
  numberstyle=\\tiny\\color{gray},
  keywordstyle=\\color{blue},
  commentstyle=\\color{green!60!black},
  stringstyle=\\color{orange},
  showstringspaces=false
}

\\title{Converted from Markdown}
\\author{}
\\date{\\today}

\\begin{document}
\\maketitle

"""
    
    # Process Markdown content
    lines = markdown_content.split('\n')
    in_code_block = False
    in_list = False
    in_ordered_list = False
    in_blockquote = False
    list_level = 0
    table_data = []
    in_table = False
    current_line_idx = 0
    total_lines = len(lines)
    
    while current_line_idx < total_lines:
        line = lines[current_line_idx]
        current_line_idx += 1
        
        # Headers
        if re.match(r'^# ', line):
            latex_content += f"\\section{{{line[2:]}}}\n\n"
        elif re.match(r'^## ', line):
            latex_content += f"\\subsection{{{line[3:]}}}\n\n"
        elif re.match(r'^### ', line):
            latex_content += f"\\subsubsection{{{line[4:]}}}\n\n"
        elif re.match(r'^#### ', line):
            latex_content += f"\\paragraph{{{line[5:]}}}\n\n"
        elif re.match(r'^##### ', line):
            latex_content += f"\\subparagraph{{{line[6:]}}}\n\n"
        
        # Images
        # ![alt text](image_path)
        elif '![' in line and '](' in line:
            alt_match = re.search(r'!\[(.*?)\]', line)
            path_match = re.search(r'\((.*?)\)', line)
            
            if alt_match and path_match:
                alt_text = alt_match.group(1)
                image_path = path_match.group(1)
                
                # Make sure path is using forward slashes for LaTeX
                image_path = image_path.replace('\\', '/')
                
                latex_content += f"""
\\begin{{figure}}[htbp]
\\centering
\\includegraphics[width=0.8\\textwidth]{{{image_path}}}
\\caption{{{alt_text}}}
\\end{{figure}}

"""
        
        # Code blocks
        elif line.startswith('```'):
            if in_code_block:
                latex_content += "\\end{lstlisting}\n\n"
                in_code_block = False
            else:
                language = line[3:].strip()
                if language:
                    latex_content += f"\\begin{{lstlisting}}[language={language}]\n"
                else:
                    latex_content += "\\begin{lstlisting}\n"
                in_code_block = True
        
        # Tables
        elif '|' in line and not in_code_block:
            if not in_table:
                # Check if this is a table header
                if re.match(r'^\|[-:| ]+\|$', lines[current_line_idx]) if current_line_idx < total_lines else False:
                    in_table = True
                    table_data = []
                    # Parse header
                    headers = [cell.strip() for cell in line.split('|')[1:-1]]
                    table_data.append(headers)
                    # Skip the separator line
                    current_line_idx += 1
            else:
                # Parse table row
                if line.startswith('|') and line.endswith('|'):
                    cells = [cell.strip() for cell in line.split('|')[1:-1]]
                    table_data.append(cells)
                else:
                    # End of table
                    latex_content += format_table(table_data)
                    in_table = False
        
        # End table if we're at the end of table data
        elif in_table:
            latex_content += format_table(table_data)
            in_table = False
            
        # Blockquotes
        elif line.startswith('> '):
            if not in_blockquote:
                latex_content += "\\begin{quote}\n"
                in_blockquote = True
            latex_content += f"{line[2:]}\n"
        elif in_blockquote and not line.startswith('> '):
            latex_content += "\\end{quote}\n\n"
            in_blockquote = False
            if line.strip():
                current_line_idx -= 1  # Process this line again
        
        # Regular text (inside or outside code blocks)
        elif in_code_block:
            latex_content += line + "\n"
        else:
            # Ordered lists
            ordered_list_match = re.match(r'^(\s*)\d+\.\s+(.*)', line)
            if ordered_list_match:
                indent, content = ordered_list_match.groups()
                indent_level = len(indent) // 2
                
                if not in_ordered_list or indent_level != list_level:
                    if in_ordered_list:
                        # Close previous list if indent level changed
                        for _ in range(list_level + 1):
                            latex_content += "\\end{enumerate}\n"
                    
                    # Start new list with proper nesting
                    for i in range(indent_level + 1):
                        latex_content += "\\begin{enumerate}\n"
                    
                    in_ordered_list = True
                    list_level = indent_level
                
                latex_content += f"\\item {content}\n"
            
            # Unordered lists
            elif re.match(r'^(\s*)- ', line):
                indent = re.match(r'^(\s*)- ', line).group(1)
                indent_level = len(indent) // 2
                content = line.strip()[2:]
                
                if not in_list or indent_level != list_level:
                    if in_list:
                        # Close previous list if indent level changed
                        for _ in range(list_level + 1):
                            latex_content += "\\end{itemize}\n"
                    
                    # Start new list with proper nesting
                    for i in range(indent_level + 1):
                        latex_content += "\\begin{itemize}\n"
                    
                    in_list = True
                    list_level = indent_level
                
                latex_content += f"\\item {content}\n"
            
            # End of lists
            elif (in_list or in_ordered_list) and line.strip() == "":
                if in_list:
                    for _ in range(list_level + 1):
                        latex_content += "\\end{itemize}\n"
                    in_list = False
                
                if in_ordered_list:
                    for _ in range(list_level + 1):
                        latex_content += "\\end{enumerate}\n"
                    in_ordered_list = False
                
                list_level = 0
                latex_content += "\n"
            
            # Bold and italic text
            elif line.strip():
                # Process inline formatting
                processed_line = process_inline_formatting(line)
                latex_content += processed_line + "\n\n"
    
    # Close any open environments
    if in_list:
        for _ in range(list_level + 1):
            latex_content += "\\end{itemize}\n"
    
    if in_ordered_list:
        for _ in range(list_level + 1):
            latex_content += "\\end{enumerate}\n"
    
    if in_blockquote:
        latex_content += "\\end{quote}\n"
    
    if in_code_block:
        latex_content += "\\end{lstlisting}\n"
    
    if in_table:
        latex_content += format_table(table_data)
    
    # Close document if preamble was included
    if include_preamble:
        latex_content += "\\end{document}"
    
    # Save to file if output path provided
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(latex_content)
    
    return latex_content


def process_inline_formatting(text: str) -> str:
    """
    Process inline Markdown formatting (bold, italic, code, links).
    """
    # Inline code
    text = re.sub(r'`([^`]+)`', r'\\texttt{\1}', text)
    
    # Bold (both ** and __ syntax)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', text)
    text = re.sub(r'__([^_]+)__', r'\\textbf{\1}', text)
    
    # Italic (both * and _ syntax)
    text = re.sub(r'\*([^*]+)\*', r'\\textit{\1}', text)
    text = re.sub(r'_([^_]+)_', r'\\textit{\1}', text)
    
    # Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\\href{\2}{\1}', text)
    
    # Escape special LaTeX characters
    special_chars = ['%', '&', '$', '#', '_', '{', '}', '~', '^']
    for char in special_chars:
        if char in text and not (char == '_' and ('\\textit{' in text or '\\textbf{' in text)):
            text = text.replace(char, f'\\{char}')
    
    return text


def format_table(table_data: List[List[str]]) -> str:
    """
    Format a Markdown table as a LaTeX table.
    """
    if not table_data or not table_data[0]:
        return ""
    
    num_cols = len(table_data[0])
    col_spec = 'c' * num_cols
    
    latex_table = f"\\begin{{table}}[htbp]\n\\centering\n\\begin{{tabular}}{{|{col_spec}|}}\n\\hline\n"
    
    # Header row
    latex_table += ' & '.join(process_inline_formatting(cell) for cell in table_data[0]) + ' \\\\ \\hline\\hline\n'
    
    # Data rows
    for row in table_data[1:]:
        # Ensure row has the right number of columns
        while len(row) < num_cols:
            row.append('')
        row = row[:num_cols]  # Truncate if too many columns
        
        latex_table += ' & '.join(process_inline_formatting(cell) for cell in row) + ' \\\\ \\hline\n'
    
    latex_table += "\\end{tabular}\n\\end{table}\n\n"
    return latex_table
