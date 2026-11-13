"""Measure a candidate against an independently generated Crystal reference."""
import re
import unicodedata
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from app.services.crystal_reports.validation import read_pdf_symbols


def words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"[\w]+(?:[.,/-][\w]+)*", normalized)


def compare(candidate: Path, reference: Path, *, retain_text: bool = False) -> dict:
    actual, expected = PdfReader(candidate), PdfReader(reference)
    actual_text = "\n".join(page.extract_text() or "" for page in actual.pages)
    expected_text = "\n".join(page.extract_text() or "" for page in expected.pages)
    missing = Counter(words(expected_text)) - Counter(words(actual_text))
    actual_codes, _ = read_pdf_symbols(candidate)
    expected_codes, _ = read_pdf_symbols(reference)
    def identity(item):
        return item["format"], item["value"]
    result = {
        "candidate_pages": len(actual.pages), "reference_pages": len(expected.pages),
        "pagination_matches": len(actual.pages) == len(expected.pages),
        "reference_tokens_missing": sum(missing.values()),
        "decoded_symbols_match_reference": bool(expected_codes) and (
            {identity(item) for item in actual_codes} == {identity(item) for item in expected_codes}),
        "visual_review_required": True, "fiscal_validation_complete": False,
    }
    if retain_text:
        result["missing_reference_tokens"] = dict(missing)
        result["decoded_candidate_symbols"] = actual_codes
        result["decoded_reference_symbols"] = expected_codes
    return result
