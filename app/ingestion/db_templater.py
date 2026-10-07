"""
Database row → natural-language sentence converter.

Each structured row (e.g. an employee salary record) is turned into a
human-readable sentence so it can be embedded and searched alongside
unstructured PDF/OCR text.
"""

_FIELD_LABELS: dict[str, str] = {
    "salary": "salary",
    "performance_review": "performance review status",
    "department": "department",
    "status": "employment status",
    "bonus": "bonus amount",
}


def row_to_sentence(row: dict) -> str:
    name = (row.get("employee_name") or "the employee").strip()
    field = (row.get("field_name") or "").strip()
    value = (row.get("field_value") or "").strip()

    label = _FIELD_LABELS.get(field, field)

    if field == "salary":
        return f"{name}'s annual salary is ${value}"
    elif field == "performance_review":
        return f"{name}'s performance review status is {value}"
    elif field == "bonus":
        return f"{name}'s bonus amount is ${value}"
    else:
        return f"{name}'s {label} is {value}"
