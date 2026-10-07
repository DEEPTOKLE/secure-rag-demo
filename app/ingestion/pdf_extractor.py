"""
PDF extraction via PyMuPDF (fitz).

Returns a list of *segments*, each containing:
    - text          : literal extracted text (not paraphrased)
    - source_type   : 'pdf'
    - exact_locator : {source, file, page, bbox}
"""

import os

import pymupdf as fitz


def extract_pdf(path: str) -> list[dict]:
    doc = fitz.open(path)
    basename = os.path.basename(path)
    segments: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block.get("type") != 0:  # 0 = text, 1 = line, 2 = free text, 3 = image
                continue

            text_parts: list[str] = []
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text_parts.append(span["text"])
            text = "".join(text_parts).strip()
            if not text:
                continue

            bbox = block["bbox"]
            segments.append(
                {
                    "text": text,
                    "source_type": "pdf",
                    "exact_locator": {
                        "source": "pdf",
                        "file": basename,
                        "page": page_num + 1,
                        "bbox": {
                            "x0": bbox[0],
                            "top": bbox[1],
                            "x1": bbox[2],
                            "bottom": bbox[3],
                        },
                    },
                }
            )

    doc.close()
    return segments
