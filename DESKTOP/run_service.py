from pathlib import Path
import sys


START = Path(__file__).resolve()
sys.path.insert(0, str(START.parents[1] / "DESKTOP"))

from automacao_novelis_desktop.root_locator import find_project_root  # noqa: E402
from automacao_novelis_desktop.service_worker import run_service  # noqa: E402


if __name__ == "__main__":
    run_service(find_project_root(START.parent))
