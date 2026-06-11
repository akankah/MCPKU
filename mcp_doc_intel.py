import os
import json
import asyncio
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("doc_intel", instructions="""
Local Document Intelligence Server: Extract text and data from PDF, DOCX, and XLSX files.
Allows the AI to 'read' office documents locally without external APIs.
""")

# Optional dependencies check
try:
    import pypdf
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import pandas as pd
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

@mcp.tool(name="read_pdf", description="Extract text content from a PDF file.")
async def read_pdf(file_path: str) -> str:
    """Reads text from a PDF file page by page."""
    if not HAS_PDF:
        return "Error: 'pypdf' not installed. Run 'pip install pypdf'."
    
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
    if not HAS_DOCX:
        return "Error: 'python-docx' not installed. Run 'pip install python-docx'."
    
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
    if not HAS_XLSX:
        return "Error: 'pandas' and 'openpyxl' not installed. Run 'pip install pandas openpyxl'."
    
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
