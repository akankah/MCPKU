import os
import json
from pathlib import Path
from PIL import Image
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("media", instructions="""
Media Processor Server: Resize, convert, and inspect image files locally.
Optimizes assets for web and mobile development.
""")

@mcp.tool(name="get_image_info", description="Get image metadata (resolution, format, mode).")
async def get_image_info(image_path: str) -> str:
    """Returns metadata for the specified image."""
    try:
        path = Path(image_path).expanduser()
        if not path.exists():
            return f"Error: File not found at {image_path}"
        
        with Image.open(path) as img:
            info = {
                "filename": path.name,
                "format": img.format,
                "mode": img.mode,
                "size": img.size,  # (width, height)
                "width": img.width,
                "height": img.height,
                "info": img.info
            }
        return json.dumps(info, indent=2, default=str)
    except Exception as e:
        return f"Error reading image: {str(e)}"

@mcp.tool(name="resize_image", description="Resize an image to specified width/height.")
async def resize_image(image_path: str, width: int, height: int, output_path: str = None) -> str:
    """Resizes image. If output_path is none, appends '_resized' to filename."""
    try:
        path = Path(image_path).expanduser()
        if not path.exists():
            return f"Error: File not found at {image_path}"
        
        if not output_path:
            output_path = str(path.parent / f"{path.stem}_resized{path.suffix}")
        
        with Image.open(path) as img:
            resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
            resized_img.save(output_path)
            
        return f"Image resized successfully to {width}x{height}. Saved at: {output_path}"
    except Exception as e:
        return f"Error resizing image: {str(e)}"

@mcp.tool(name="convert_image", description="Convert an image to another format (e.g., PNG to WebP).")
async def convert_image(image_path: str, target_format: str, output_path: str = None) -> str:
    """Converts image format (webp, png, jpeg, etc.)."""
    try:
        path = Path(image_path).expanduser()
        if not path.exists():
            return f"Error: File not found at {image_path}"
        
        target_format = target_format.lower()
        if not output_path:
            output_path = str(path.parent / f"{path.stem}.{target_format}")
            
        with Image.open(path) as img:
            # Handle RGBA to RGB conversion for formats like JPEG
            if target_format in ["jpg", "jpeg"] and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output_path, format=target_format.upper() if target_format != "jpg" else "JPEG")
            
        return f"Image converted to {target_format} successfully. Saved at: {output_path}"
    except Exception as e:
        return f"Error converting image: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
