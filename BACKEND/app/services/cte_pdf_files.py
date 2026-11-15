"""Find a PDF for the exact filial/serie/documento in current and legacy folders."""

from pathlib import Path

from app.automation.cancellation import check_cancelled


def pdf_target(directory: Path, row: dict) -> Path:
    cte = "-".join(str(int(row[key])) for key in ("filial", "serie", "documento"))
    return directory / f"cte-{int(row['documento'])}" / f"CTE_{cte}.pdf"


def find_pdf_evidence(directory: Path, row: dict, *, files=None, validator=None) -> Path | None:
    cte = "-".join(str(int(row[key])) for key in ("filial", "serie", "documento"))
    folder = pdf_target(directory, row).parent
    legacy = directory / f"cte_{int(row['documento'])}"
    for base in (folder, directory, legacy):
        available = {path.name.casefold(): path for path in files(base, {".pdf"})} if files else None
        for name in (f"CTE_{cte}.pdf", f"{cte}.pdf", f"cte_{cte.replace('-', '_')}.pdf"):
            check_cancelled()
            path = available.get(name.casefold()) if available is not None else base / name
            if path is None:
                continue
            try:
                if validator is not None:
                    if validator(path):
                        return path
                    continue
                if available is not None or path.is_file() and path.stat().st_size > 5:
                    with path.open("rb") as file:
                        header = file.read(6)
                        if len(header) > 5 and header.startswith(b"%PDF-"):
                            return path
            except OSError:
                continue
    return None
