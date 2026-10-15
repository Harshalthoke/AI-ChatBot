"""PDF text extraction and academic section parsing using PyMuPDF."""

import re
import io
from typing import Dict, Any, Optional, List
import pymupdf  # fitz

MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails due to format, corruption, or size."""
    pass


def extract_text_from_pdf_stream(file_stream: io.BytesIO, max_size_bytes: int = MAX_PDF_SIZE_BYTES) -> Dict[str, Any]:
    """Extracts raw text and parsed academic sections from a PDF stream or byte buffer."""
    # Check size
    file_stream.seek(0, io.SEEK_END)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > max_size_bytes:
        raise PDFExtractionError(f"PDF file size ({size / (1024*1024):.2f} MB) exceeds maximum allowed size ({max_size_bytes / (1024*1024):.1f} MB).")

    # Verify PDF magic header
    header = file_stream.read(5)
    file_stream.seek(0)
    if not header.startswith(b"%PDF-"):
        raise PDFExtractionError("Invalid file format. File does not appear to be a valid PDF document.")

    try:
        doc = pymupdf.open(stream=file_stream.read(), filetype="pdf")
    except Exception as e:
        raise PDFExtractionError(f"Failed to open PDF document: {e}")

    if doc.page_count == 0:
        raise PDFExtractionError("PDF contains zero pages.")

    pages_text: List[str] = []
    first_page_blocks: List[str] = []

    for page_idx in range(min(doc.page_count, 40)):  # Read up to 40 pages
        page = doc.load_page(page_idx)
        text = page.get_text("text")
        pages_text.append(text)
        if page_idx == 0:
            blocks = page.get_text("blocks")
            # blocks are tuples (x0, y0, x1, y1, text, block_no, block_type)
            first_page_blocks = [b[4].strip() for b in blocks if len(b) > 4 and b[4].strip()]

    full_text = "\n\n".join(pages_text).strip()
    first_page_text = pages_text[0] if pages_text else ""

    # Parse academic metadata
    title, abstract, keywords = _parse_academic_header(first_page_blocks, first_page_text, full_text)

    return {
        "full_text": full_text,
        "first_page_text": first_page_text,
        "page_count": doc.page_count,
        "word_count": len(full_text.split()),
        "extracted_title": title,
        "extracted_abstract": abstract,
        "extracted_keywords": keywords,
    }


def _parse_academic_header(
    blocks: List[str],
    first_page_text: str,
    full_text: str
) -> tuple[Optional[str], Optional[str], List[str]]:
    """Heuristically extracts Title, Abstract, and Keywords from academic papers."""
    title: Optional[str] = None
    abstract: Optional[str] = None
    keywords: List[str] = []

    # 1. Title Heuristic: First prominent block on page 1 that is not a journal header/page number
    for block in blocks[:5]:
        cleaned = block.strip()
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            continue
        candidate = " ".join(lines)
        # Avoid common header tokens
        lower_cand = candidate.lower()
        if any(h in lower_cand for h in ["arxiv:", "doi.org", "issn", "volume", "issue", "http://", "https://"]):
            continue
        if len(candidate.split()) >= 3 and len(candidate) < 300:
            title = candidate
            break

    # 2. Abstract Extraction: Look for 'Abstract' keyword
    abstract_match = re.search(
        r"(?:Abstract|ABSTRACT)[:\s\-\—]+(.*?)(?=\n\s*(?:Keywords|Index Terms|1\.\s+Introduction|Introduction|1\s+Introduction)|$)",
        full_text,
        re.DOTALL | re.IGNORECASE
    )
    if abstract_match:
        abstract_candidate = abstract_match.group(1).strip()
        # Clean up whitespace
        abstract_candidate = re.sub(r"\s+", " ", abstract_candidate)
        if len(abstract_candidate.split()) >= 15:
            abstract = abstract_candidate

    # 3. Keywords Extraction
    kw_match = re.search(
        r"(?:Keywords|Index Terms|Key words)[:\s\-\—]+(.*?)(?=\n\s*(?:1\.\s+Introduction|Introduction|1\s+Introduction|I\.\s+INTRODUCTION)|$)",
        full_text,
        re.DOTALL | re.IGNORECASE
    )
    if kw_match:
        kw_text = kw_match.group(1).strip()
        # Split by comma, semicolon, bullet, or newline
        raw_parts = re.split(r"[,;•\n\t]+", kw_text)
        for part in raw_parts:
            p = re.sub(r"\s+", " ", part).strip()
            # Stop if reached intro text
            if len(p) > 50 or "introduction" in p.lower():
                break
            if len(p) >= 2:
                keywords.append(p)

    return title, abstract, keywords


def extract_metadata_from_text(text: str) -> Dict[str, Any]:
    """Extracts title, abstract, and keywords from academic text."""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    first_page_text = blocks[0] if blocks else ""
    title, abstract, keywords = _parse_academic_header(blocks, first_page_text, text)
    return {
        "title": title or (blocks[0][:150] if blocks else "Untitled Paper"),
        "abstract": abstract or (blocks[1][:500] if len(blocks) > 1 else ""),
        "keywords": keywords or []
    }


def extract_text_from_pdf_bytes(pdf_bytes: bytes, max_size_bytes: int = MAX_PDF_SIZE_BYTES) -> Dict[str, Any]:
    """Convenience helper to extract text and sections directly from bytes."""
    try:
        stream = io.BytesIO(pdf_bytes)
        return extract_text_from_pdf_stream(stream, max_size_bytes=max_size_bytes)
    except PDFExtractionError as e:
        return {
            "full_text": "",
            "first_page_text": "",
            "page_count": 0,
            "word_count": 0,
            "extracted_title": None,
            "extracted_abstract": None,
            "extracted_keywords": [],
            "error": str(e)
        }
    except Exception as e:
        return {
            "full_text": "",
            "first_page_text": "",
            "page_count": 0,
            "word_count": 0,
            "extracted_title": None,
            "extracted_abstract": None,
            "extracted_keywords": [],
            "error": str(e)
        }

