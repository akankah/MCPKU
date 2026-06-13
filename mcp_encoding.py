"""
mcp_encoding.py — MCP Server for Character Encoding Conversion
==============================================================
Tools for encoding/decoding text in various character encodings,
Unicode normalization, escaping, base64/hex, and mojibake repair.

Single-file, stdlib-first (codecs, unicodedata).
chardet optional for auto-detection.
"""

import base64
import binascii
import codecs
import json
import re
import unicodedata
from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    import chardet as _chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

mcp = FastMCP("encoding", instructions="""
Character encoding tools for developers. Convert text between encodings,
detect encoding of raw bytes, normalize Unicode, escape/unescape,
encode to base64/hex/URL, and repair mojibake (garbled text).

Available standard encodings: utf-8, latin-1, cp1252, shift_jis,
euc-jp, euc-kr, gb2312, gbk, big5, iso-2022-jp, koi8-r, etc.
Use list_encodings() to see all supported codecs.
""")


# ── Helpers ──────────────────────────────────────────────────────────────────

_ASCII_RE = re.compile(r"[\\]u([0-9a-fA-F]{4})")
_ASCII_RE2 = re.compile(r"[\\]U([0-9a-fA-F]{8})")
_ALT_ENC = [
    ("utf-8", "latin-1"),
    ("latin-1", "utf-8"),
    ("utf-8", "cp1252"),
    ("cp1252", "utf-8"),
    ("shift_jis", "utf-8"),
    ("utf-8", "shift_jis"),
    ("euc-kr", "utf-8"),
    ("utf-8", "euc-kr"),
    ("gbk", "utf-8"),
    ("utf-8", "gbk"),
    ("iso-2022-jp", "utf-8"),
    ("utf-8", "iso-2022-jp"),
    ("koi8-r", "utf-8"),
    ("utf-8", "koi8-r"),
    ("utf-8", "iso-8859-1"),
    ("iso-8859-1", "utf-8"),
]


def _py_encodings() -> list[str]:
    return sorted(set(codecs.alias_names))


def _decode_bytes(data: bytes, enc: str) -> str | None:
    try:
        return data.decode(enc)
    except (UnicodeDecodeError, LookupError):
        return None


def _encode_str(text: str, enc: str) -> bytes | None:
    try:
        return text.encode(enc)
    except (UnicodeEncodeError, LookupError):
        return None


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(name="list_encodings",
          description="List all available encodings. Optionally filter by search term.")
async def list_encodings(search: str = "") -> str:
    encs = _py_encodings()
    if search:
        encs = [e for e in encs if search.lower() in e.lower()]
    return json.dumps({"count": len(encs), "encodings": encs}, ensure_ascii=False)


@mcp.tool(name="convert_encoding",
          description="Convert text between character encodings. Provide bytes as hex string or raw text.")
async def convert_encoding(
    text: str = "",
    bytes_hex: str = "",
    from_encoding: str = "utf-8",
    to_encoding: str = "utf-8",
) -> str:
    if bytes_hex:
        try:
            raw = binascii.unhexlify(bytes_hex.replace(" ", ""))
        except binascii.Error as e:
            return json.dumps({"error": f"Invalid hex: {e}"}, ensure_ascii=False)
    else:
        raw = text.encode("utf-8") if from_encoding == "utf-8" else _encode_str(text, from_encoding)
        if raw is None:
            return json.dumps({"error": f"Cannot encode input as {from_encoding}"}, ensure_ascii=False)

    decoded = _decode_bytes(raw, from_encoding)
    if decoded is None:
        return json.dumps({"error": f"Cannot decode bytes as {from_encoding}"}, ensure_ascii=False)

    out_bytes = _encode_str(decoded, to_encoding)
    if out_bytes is None:
        return json.dumps({"error": f"Cannot encode to {to_encoding}"}, ensure_ascii=False)

    return json.dumps({
        "text": decoded,
        "encoded": to_encoding,
        "bytes_hex": binascii.hexlify(out_bytes).decode("ascii"),
        "bytes_length": len(out_bytes),
    }, ensure_ascii=False)


@mcp.tool(name="detect_encoding",
          description="Detect character encoding of raw bytes (hex string). Uses chardet if available, falls back to heuristic.")
async def detect_encoding(bytes_hex: str) -> str:
    try:
        raw = binascii.unhexlify(bytes_hex.replace(" ", ""))
    except binascii.Error as e:
        return json.dumps({"error": f"Invalid hex: {e}"}, ensure_ascii=False)

    results = []

    if HAS_CHARDET:
        det = _chardet.detect(raw)
        results.append({
            "encoding": det.get("encoding", "unknown"),
            "confidence": det.get("confidence", 0),
            "source": "chardet",
        })

    for enc in ["utf-8", "latin-1", "cp1252", "shift_jis", "euc-jp", "euc-kr", "gbk", "big5", "koi8-r"]:
        try:
            raw.decode(enc)
            results.append({
                "encoding": enc,
                "confidence": None,
                "source": "stdlib",
            })
        except (UnicodeDecodeError, LookupError):
            pass

    return json.dumps({"bytes_length": len(raw), "detections": results}, ensure_ascii=False)


@mcp.tool(name="unicode_normalize",
          description="Normalize Unicode text: NFC, NFD, NFKC, NFKD.")
async def unicode_normalize(text: str, form: str = "NFC") -> str:
    form = form.upper().strip()
    if form not in ("NFC", "NFD", "NFKC", "NFKD"):
        return json.dumps({"error": f"Invalid form: {form}. Use NFC, NFD, NFKC, NFKD."}, ensure_ascii=False)
    normalized = unicodedata.normalize(form, text)
    return json.dumps({
        "input": text,
        "form": form,
        "output": normalized,
        "input_length": len(text),
        "output_length": len(normalized),
        "characters": [{"char": c, "name": unicodedata.name(c, "<unknown>"), "code": f"U+{ord(c):04X}"} for c in normalized[:50]],
    }, ensure_ascii=False)


@mcp.tool(name="unicode_escape",
          description="Escape Unicode characters to \\uXXXX or \\UXXXXXXXX notation.")
async def unicode_escape(text: str, ascii_only: bool = True) -> str:
    if ascii_only:
        escaped = text.encode("ascii", errors="backslashreplace").decode("ascii")
    else:
        escaped = json.dumps(text, ensure_ascii=False)[1:-1]
    return json.dumps({"input": text, "escaped": escaped}, ensure_ascii=False)


@mcp.tool(name="unicode_unescape",
          description="Unescape \\uXXXX / \\UXXXXXXXX / \\xXX sequences back to characters.")
async def unicode_unescape(text: str) -> str:
    def _replace(m):
        return chr(int(m.group(1), 16))
    s = _ASCII_RE.sub(_replace, text)
    s = _ASCII_RE2.sub(_replace, s)
    s = s.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
    s = s.replace("\\\\", "\\")
    try:
        s = s.encode("utf-8").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return json.dumps({"input": text, "unescaped": s}, ensure_ascii=False)


@mcp.tool(name="encode_base64",
          description="Base64 encode or decode text/bytes.")
async def encode_base64(
    text: str = "",
    bytes_hex: str = "",
    action: str = "encode",
) -> str:
    if action == "encode":
        if bytes_hex:
            try:
                raw = binascii.unhexlify(bytes_hex.replace(" ", ""))
            except binascii.Error as e:
                return json.dumps({"error": f"Invalid hex: {e}"}, ensure_ascii=False)
        else:
            raw = text.encode("utf-8")
        out = base64.b64encode(raw).decode("ascii")
        return json.dumps({"action": "encode", "output": out}, ensure_ascii=False)
    else:
        try:
            raw = base64.b64decode(text)
        except Exception as e:
            return json.dumps({"error": f"Invalid base64: {e}"}, ensure_ascii=False)
        return json.dumps({
            "action": "decode",
            "text": raw.decode("utf-8", errors="replace"),
            "bytes_hex": binascii.hexlify(raw).decode("ascii"),
        }, ensure_ascii=False)


@mcp.tool(name="encode_hex",
          description="Hex encode or decode text/bytes.")
async def encode_hex(
    text: str = "",
    bytes_hex: str = "",
    action: str = "encode",
) -> str:
    if action == "encode":
        if bytes_hex:
            try:
                raw = binascii.unhexlify(bytes_hex.replace(" ", ""))
            except binascii.Error as e:
                return json.dumps({"error": f"Invalid hex: {e}"}, ensure_ascii=False)
        else:
            raw = text.encode("utf-8")
        out = binascii.hexlify(raw).decode("ascii")
        return json.dumps({"action": "encode", "output": out}, ensure_ascii=False)
    else:
        try:
            raw = binascii.unhexlify(text.replace(" ", ""))
        except binascii.Error as e:
            return json.dumps({"error": f"Invalid hex: {e}"}, ensure_ascii=False)
        return json.dumps({
            "action": "decode",
            "text": raw.decode("utf-8", errors="replace"),
            "bytes_hex": binascii.hexlify(raw).decode("ascii"),
        }, ensure_ascii=False)


@mcp.tool(name="encode_url",
          description="URL percent-encode or percent-decode a string.")
async def encode_url(text: str, action: str = "encode") -> str:
    from urllib.parse import quote, unquote
    if action == "encode":
        out = quote(text, safe="")
        return json.dumps({"action": "encode", "output": out}, ensure_ascii=False)
    else:
        out = unquote(text)
        return json.dumps({"action": "decode", "output": out}, ensure_ascii=False)


@mcp.tool(name="repair_encoding",
          description="Try to repair mojibake (garbled text). Tests common encoding mis-pairs and returns best guess.")
async def repair_encoding(text: str, top_n: int = 5) -> str:
    raw = text.encode("utf-8", errors="replace")
    candidates = []
    for src, tgt in _ALT_ENC:
        decoded = _decode_bytes(raw, src)
        if decoded is None:
            continue
        re_encoded = _encode_str(decoded, tgt)
        if re_encoded is None:
            continue
        try:
            roundtrip = re_encoded.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            continue
        score = sum(1 for c in roundtrip if unicodedata.category(c) != "Cc")
        candidates.append({
            "guessed_from": src,
            "guessed_to": tgt,
            "text": roundtrip,
            "score": score,
        })
    candidates.sort(key=lambda x: -x["score"])
    return json.dumps({
        "input": text,
        "candidates": candidates[:top_n],
    }, ensure_ascii=False)


@mcp.tool(name="char_info",
          description="Get Unicode info for one or more characters: code point, name, category, normalization forms.")
async def char_info(characters: str) -> str:
    results = []
    for c in characters:
        cp = ord(c)
        results.append({
            "char": c,
            "code": f"U+{cp:04X}",
            "decimal": cp,
            "name": unicodedata.name(c, "<unknown>"),
            "category": unicodedata.category(c),
            "combining": unicodedata.combining(c),
            "bidirectional": unicodedata.bidirectional(c),
            "mirrored": unicodedata.mirrored(c),
            "decomposition": unicodedata.decomposition(c),
            "nfc": unicodedata.normalize("NFC", c),
            "nfd": unicodedata.normalize("NFD", c),
            "nfkc": unicodedata.normalize("NFKC", c),
            "nfkd": unicodedata.normalize("NFKD", c),
        })
    return json.dumps({"count": len(results), "characters": results}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
