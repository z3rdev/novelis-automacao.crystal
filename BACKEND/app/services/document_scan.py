"""Batch filesystem reads for one plan, sharing directory listings across workers."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from app.automation.cancellation import check_cancelled

PROOF_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def scan_evidence(builder, rows, pdf, xml, proofs):
    if not rows:
        return []
    roots = (
        (
            builder._resolve(pdf.get("downloadTargetDir") or "captures/rodopar-pdfs-downloads"),
            {".pdf"},
        ),
        (builder._resolve(xml.get("downloadDir") or "captures/cte-fazenda-downloads"), {".xml"}),
        (
            builder._resolve(proofs.get("targetDir") or "captures/tarifario-downloads"),
            PROOF_EXTENSIONS,
        ),
    )

    def prepare(directory, extensions):
        check_cancelled()
        if str(directory).startswith("\\\\") and not directory.is_dir():
            raise OSError("Pasta configurada de documentos indisponivel.")
        builder._all_files(directory, extensions)

    # Roots are independent SMB directories. Complete their listings before
    # checking children so nonexistent legacy folders need no network request.
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="document-check") as executor:
        pending = [
            executor.submit(copy_context().run, prepare, root, extensions)
            for root, extensions in roots
        ]
        for future in pending:
            future.result()
        pending = [
            executor.submit(copy_context().run, builder.resolve_evidence, row, pdf, xml, proofs)
            for row in rows
        ]
        return [future.result() for future in pending]
