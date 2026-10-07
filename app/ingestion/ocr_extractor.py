"""
OCR extraction via pytesseract + Pillow.

Returns a list of *segments*, each containing:
    - text          : extracted text
    - source_type   : 'ocr'
    - confidence    : average word confidence for the line (0-100)
    - exact_locator : {source, file, region}
"""

import os
from collections import OrderedDict

import pytesseract
from PIL import Image

from app.config import TESSERACT_CMD

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def extract_image(path: str) -> list[dict]:
    img = Image.open(path)
    basename = os.path.basename(path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Group word-level results into lines
    lines: "OrderedDict[tuple, dict]" = OrderedDict()
    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        if not word:
            continue

        line_key = (
            data["page_num"][i],
            data["block_num"][i],
            data["par_num"][i],
            data["line_num"][i],
        )

        if line_key not in lines:
            lines[line_key] = {
                "text": "",
                "confidences": [],
                "bbox": [float("inf"), float("inf"), 0, 0],
            }

        line = lines[line_key]
        line["text"] += (" " + word if line["text"] else word)
        line["confidences"].append(data["conf"][i])

        # Expand bounding box to cover this word
        x0 = data["left"][i]
        y0 = data["top"][i]
        x1 = x0 + data["width"][i]
        y1 = y0 + data["height"][i]
        line["bbox"][0] = min(line["bbox"][0], x0)
        line["bbox"][1] = min(line["bbox"][1], y0)
        line["bbox"][2] = max(line["bbox"][2], x1)
        line["bbox"][3] = max(line["bbox"][3], y1)

    segments: list[dict] = []
    for key, line in lines.items():
        valid_confs = [c for c in line["confidences"] if c != -1]
        avg_conf = sum(valid_confs) / len(valid_confs) if valid_confs else 0.0

        x0, y0, x1, y1 = line["bbox"]
        segments.append(
            {
                "text": line["text"].strip(),
                "source_type": "ocr",
                "confidence": avg_conf,
                "exact_locator": {
                    "source": "ocr",
                    "file": basename,
                    "region": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                },
            }
        )

    img.close()
    return segments
