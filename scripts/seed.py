"""
Seed script: populate the database with demo data and documents.

Creates:
    • HR-only PDF (native text) → chunks visible to hr_manager + admin
    • Finance-only scanned image (OCR) → chunks visible to finance_manager + admin
    • 10 employee_records rows (5 salary = finance-only, 5 review = hr-only)

Usage:
    python scripts/seed.py
"""

import json
import os
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db_session
from app.ingestion.pipeline import (
    insert_employee_records,
    process_db_records,
    process_image,
    process_pdf,
    read_employee_records,
)

SEED_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_data")
HR_PDF_PATH = os.path.join(SEED_DATA_DIR, "hr_policy.pdf")
FINANCE_PNG_PATH = os.path.join(SEED_DATA_DIR, "finance_scan.png")

ALLOWED_HR = ["1", "hr_manager", "3", "admin"]
ALLOWED_FINANCE = ["2", "finance_manager", "3", "admin"]


# ─── Demo data definitions ────────────────────────────────────────────

EMPLOYEE_RECORDS = [
    # ── Finance-visible (salary) ──
    {"employee_name": "John Smith", "field_name": "salary", "field_value": "85000",
     "allowed_principals": ALLOWED_FINANCE, "raw_text": "John Smith's annual salary is $85,000",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "salary"},
     "tenant_id": 1},
    {"employee_name": "Jane Doe", "field_name": "salary", "field_value": "92000",
     "allowed_principals": ALLOWED_FINANCE, "raw_text": "Jane Doe's annual salary is $92,000",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "salary"},
     "tenant_id": 1},
    {"employee_name": "David Wilson", "field_name": "salary", "field_value": "78000",
     "allowed_principals": ALLOWED_FINANCE, "raw_text": "David Wilson's annual salary is $78,000",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "salary"},
     "tenant_id": 1},
    {"employee_name": "Alice Brown", "field_name": "salary", "field_value": "75000",
     "allowed_principals": ALLOWED_FINANCE, "raw_text": "Alice Brown's annual salary is $75,000",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "salary"},
     "tenant_id": 1},
    {"employee_name": "Carol Davis", "field_name": "salary", "field_value": "88000",
     "allowed_principals": ALLOWED_FINANCE, "raw_text": "Carol Davis's annual salary is $88,000",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "salary"},
     "tenant_id": 1},
    # ── HR-visible (performance review) ──
    {"employee_name": "John Smith", "field_name": "performance_review", "field_value": "Exceeds Expectations",
     "allowed_principals": ALLOWED_HR, "raw_text": "John Smith's performance review status is Exceeds Expectations",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "performance_review"},
     "tenant_id": 1},
    {"employee_name": "Jane Doe", "field_name": "performance_review", "field_value": "Meets Expectations",
     "allowed_principals": ALLOWED_HR, "raw_text": "Jane Doe's performance review status is Meets Expectations",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "performance_review"},
     "tenant_id": 1},
    {"employee_name": "David Wilson", "field_name": "performance_review", "field_value": "Below Expectations",
     "allowed_principals": ALLOWED_HR, "raw_text": "David Wilson's performance review status is Below Expectations",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "performance_review"},
     "tenant_id": 1},
    {"employee_name": "Alice Brown", "field_name": "performance_review", "field_value": "Exceeds Expectations",
     "allowed_principals": ALLOWED_HR, "raw_text": "Alice Brown's performance review status is Exceeds Expectations",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "performance_review"},
     "tenant_id": 1},
    {"employee_name": "Carol Davis", "field_name": "performance_review", "field_value": "Meets Expectations",
     "allowed_principals": ALLOWED_HR, "raw_text": "Carol Davis's performance review status is Meets Expectations",
     "exact_locator": {"source": "db", "table": "employee_records", "field_name": "performance_review"},
     "tenant_id": 1},
]


def generate_hr_pdf(path: str) -> None:
    """Create a native-text PDF with HR policy content."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter
    y = height - 72

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, "HR Policy Document — Company XYZ")
    y -= 50

    c.setFont("Helvetica", 13)
    c.drawString(72, y, "Performance Reviews:")
    y -= 24
    c.setFont("Helvetica", 11)
    c.drawString(72, y, "All full-time employees undergo an annual performance review. Reviews are")
    c.drawString(72, y - 14, "conducted by direct supervisors and must be submitted to HR within 30 days")
    c.drawString(72, y - 28, "of completion. Performance ratings include: Below Expectations, Meets")
    c.drawString(72, y - 42, "Expectations, and Exceeds Expectations.")
    y -= 70

    c.setFont("Helvetica-Bold", 11)
    c.drawString(72, y, "Employee Records:")
    y -= 16
    c.setFont("Helvetica", 11)
    c.drawString(72, y, "John Smith's most recent performance review: Exceeds Expectations (2024).")
    c.drawString(72, y - 14, "Jane Doe's most recent performance review: Meets Expectations (2024).")
    y -= 40

    c.setFont("Helvetica-Bold", 13)
    c.drawString(72, y, "Complaint Reporting:")
    y -= 24
    c.setFont("Helvetica", 11)
    c.drawString(72, y, "Employee complaints should be reported to the HR manager within 48 hours.")

    c.showPage()
    c.save()
    print(f"  Generated HR policy PDF -> {path}")


def generate_finance_png(path: str) -> None:
    """Create a scanned-image-style finance report (requires OCR)."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 600), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 15)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
        small_font = font

    lines = [
        ("Q3 2024 Compensation Report", font, (1, 1, 1)),
        ("", font, (1, 1, 1)),
        ("John Smith - Salary: $85,000", font, (1, 1, 1)),
        ("Jane Doe - Salary: $92,000", font, (1, 1, 1)),
        ("David Wilson - Salary: $78,000", font, (1, 1, 1)),
        ("Alice Brown - Salary: $75,000", font, (1, 1, 1)),
        ("Carol Davis - Salary: $88,000", font, (1, 1, 1)),
        ("", font, (1, 1, 1)),
        ("Total Bonus Pool: $50,000", font, (1, 1, 1)),
        ("Finance report Q3 2024: Revenue $1.2M, expenses $800K", small_font, (1, 1, 1)),
    ]

    y = 40
    for text_line, fnt, color in lines:
        draw.text((50, y), text_line, fill=color, font=fnt)
        y += 26

    # Add a faint paper texture effect
    for _ in range(300):
        x = 50 + int(680 * np_random())
        yy = 40 + int(y * np_random())
        if yy < 560:
            alpha = int(30 * np_random())
            draw.point((x, yy), fill=(alpha, alpha, alpha))

    img.save(path)
    print(f"  Generated finance scan PNG -> {path}")


def np_random():
    import random
    return random.random()


def main() -> None:
    os.makedirs(SEED_DATA_DIR, exist_ok=True)

    # 1. Generate demo files if they don't exist
    if not os.path.exists(HR_PDF_PATH):
        generate_hr_pdf(HR_PDF_PATH)
    if not os.path.exists(FINANCE_PNG_PATH):
        generate_finance_png(FINANCE_PNG_PATH)

    # 2. Seed database using admin context
    print("Seeding database (admin context)...")

    admin_claims = {"user_id": "3", "role": "admin", "tenant_id": "1"}

    with get_db_session(admin_claims) as db:
        # Clear existing data
        db.execute(text("DELETE FROM chunks"))
        db.execute(text("DELETE FROM employee_records"))
        print("  Cleared existing data.")

        # Insert employee records (raw structured data)
        record_ids = insert_employee_records(EMPLOYEE_RECORDS, db)
        print(f"  Inserted {len(record_ids)} employee records.")

        # Read back (admin can see all rows despite RLS)
        rows = read_employee_records(db, tenant_id=1)

        # Process employee records → chunks (each inherits row-level allowed_principals)
        db_chunk_ids = process_db_records(rows, "employee_records", db)
        print(f"  Created {len(db_chunk_ids)} chunks from employee records.")

        # Process HR PDF → chunks
        hr_chunk_ids = process_pdf(
            HR_PDF_PATH, 1, ALLOWED_HR, "hr_policy.pdf", db
        )
        print(f"  Created {len(hr_chunk_ids)} HR chunks from PDF.")

        # Process finance scan → chunks (OCR)
        ocr_chunk_ids = process_image(
            FINANCE_PNG_PATH, 1, ALLOWED_FINANCE, "finance_scan.png", db
        )
        print(f"  Created {len(ocr_chunk_ids)} finance chunks from OCR.")

    # 3. Summary
    total = len(db_chunk_ids) + len(hr_chunk_ids) + len(ocr_chunk_ids)
    print(f"\nSeeding complete: {total} chunks total.")
    print(f"  - HR  chunks (pdf): {len(hr_chunk_ids)} - visible to HR + admin")
    print(f"  - Finance chunks (ocr): {len(ocr_chunk_ids)} - visible to finance + admin")
    print(f"  - DB  chunks (records): {len(db_chunk_ids)} - mix of HR + finance")
    print("\nDemo users:")
    print("  - alice (user_id=1, role=hr_manager)")
    print("  - bob   (user_id=2, role=finance_manager)")
    print("  - carol (user_id=3, role=admin)")
    print("\nSuggested question: 'What is John Smith's salary and performance review status?'")
    print("  - alice sees performance review, salary is 'not found in accessible documents'")
    print("  - carol sees both")


if __name__ == "__main__":
    main()
