import importlib
import os
import json
import asyncio
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("doc_intel", instructions="""
Local Document Intelligence Server: Extract text and data from PDF, DOCX, and XLSX files.
Allows the AI to 'read' office documents locally without external APIs.
""")

# Lazy optional deps — import on first use to avoid startup hangs when
# 28 MCP servers load C extensions simultaneously on Windows.
_HAS_PDF: bool | None = None
_HAS_DOCX: bool | None = None
_HAS_XLSX: bool | None = None

def _check_pdf():
    global _HAS_PDF
    if _HAS_PDF is None:
        try:
            import pypdf
            _HAS_PDF = True
        except ImportError:
            _HAS_PDF = False
    return _HAS_PDF

def _check_docx():
    global _HAS_DOCX
    if _HAS_DOCX is None:
        try:
            from docx import Document
            _HAS_DOCX = True
        except ImportError:
            _HAS_DOCX = False
    return _HAS_DOCX

def _check_xlsx():
    global _HAS_XLSX
    if _HAS_XLSX is None:
        try:
            import pandas as pd
            _HAS_XLSX = True
        except ImportError:
            _HAS_XLSX = False
    return _HAS_XLSX

@mcp.tool(name="read_pdf", description="Extract text content from a PDF file.")
async def read_pdf(file_path: str) -> str:
    """Reads text from a PDF file page by page."""
    if not _check_pdf():
        return "Error: 'pypdf' not installed. Run 'pip install pypdf'."
    import pypdf
    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found at {file_path}"
        
        text_content = []
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_content.append(f"--- Page {i+1} ---\\n{page_text}")
        
        return "\\n\\n".join(text_content) if text_content else "No text found in PDF."
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

@mcp.tool(name="read_docx", description="Extract text content from a Word document (.docx).")
async def read_docx(file_path: str) -> str:
    """Reads text from a DOCX file."""
    if not _check_docx():
        return "Error: 'python-docx' not installed. Run 'pip install python-docx'."
    from docx import Document
    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found at {file_path}"
        
        doc = Document(path)
        text = [para.text for para in doc.paragraphs]
        return "\\n".join(text)
    except Exception as e:
        return f"Error reading DOCX: {str(e)}"

@mcp.tool(name="read_xlsx", description="Extract data from an Excel spreadsheet (.xlsx).")
async def read_xlsx(file_path: str, sheet_name: str = 0) -> str:
    """Reads data from an Excel file and returns as JSON-formatted string."""
    if not _check_xlsx():
        return "Error: 'pandas' and 'openpyxl' not installed. Run 'pip install pandas openpyxl'."
    import pandas as pd
    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found at {file_path}"
        
        df = pd.read_excel(path, sheet_name=sheet_name)
        # Convert to markdown table for better readability for AI
        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error reading XLSX: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
