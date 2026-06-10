import os
import json
import asyncio
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Note: Requires 'pytesseract' or 'easyocr'. 
# We'll implement with a fallback logic for demo purposes.
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

mcp = FastMCP("ocr", instructions="""
Local OCR Server: Extract text from images and PDFs without external API keys.
Requires Tesseract OCR installed on the system path.
""")

@mcp.tool(name="extract_text_from_image", description="Extract text from an image file (PNG, JPG, etc.)")
async def extract_text_from_image(image_path: str) -> str:
    \"\"\"Extracts text from the given image path using Tesseract.\"\"\"
    if not HAS_OCR:
        return "Error: OCR dependencies (pytesseract/PIL) not installed. Run 'pip install pytesseract Pillow'."
    
    try:
        path = Path(image_path).expanduser()
        if not path.exists():
            return f"Error: File not found at {image_path}"
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, lambda: pytesseract.image_to_string(Image.open(path)))
        
        return f"--- Extracted Text from {path.name} ---\\n\\n{text}"
    except Exception as e:
        return f"Error during OCR: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
