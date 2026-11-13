"""Find a PDF for the exact filial/serie/documento in current and legacy folders."""

from pathlib import Path

from app.automation.cancellation import check_cancelled


def find_pdf_evidence(directory: Path, row: dict) -> Path | None:
    cte = "-".join(str(int(row[key])) for key in ("filial", "serie", "documento"))
    legacy = directory / f"cte-{int(row['documento'])}"
    for base in (directory, legacy):
        for name in (f"CTE_{cte}.pdf", f"{cte}.pdf"):
            check_cancelled()
            path = base / name
            try:
                if path.is_file() and path.stat().st_size > 5:
                    with path.open("rb") as file:
                        if file.read(5) == b"%PDF-":
                            return path
            except OSError:
                continue
    return None
