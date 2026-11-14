"""Prepare local release metadata for an existing Cargo Hub installer."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))

from app.services.releases.manifest import ReleaseManifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.installer.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise SystemExit("O arquivo precisa ser um instalador Windows.")
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = ReleaseManifest(version=args.version,
        title=f"Cargo Hub {args.version}",
        notes=args.notes_file.read_text(encoding="utf-8-sig"),
        published_at=datetime.now(timezone.utc), file=args.installer.name,
        size=args.installer.stat().st_size, sha256=digest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Manifesto local preparado. A publicação é uma etapa separada.")


if __name__ == "__main__":
    main()
