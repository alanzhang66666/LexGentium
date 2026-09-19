"""Keep generated documents separate from user prompts and process transcripts."""
from typing import Any


def dialog_text(history: Any) -> str:
    return "\n".join(
        str(row.get("message") or row.get("content") or row.get("text") or "").strip()
        for row in history or [] if isinstance(row, dict)
    ).strip()


def final_document(history: Any) -> str:
    """Only the last backend-confirmed Final turn is a document to score."""
    for row in reversed(history or []):
        if isinstance(row, dict) and row.get("role") == "Final":
            return dialog_text([row])
    return ""


def prediction_document(prediction: dict) -> str:
    # Offline evaluation files can explicitly provide their generated document.
    for key in ("model_output", "generated_doc"):
        value = prediction.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return final_document(prediction.get("dialog_history"))
