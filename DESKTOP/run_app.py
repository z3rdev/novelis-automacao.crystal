from pathlib import Path
import sys


START = Path(__file__).resolve()
sys.path.insert(0, str(START.parents[1] / "DESKTOP"))

from automacao_novelis_desktop.config import load_settings, save_settings, set_password  # noqa: E402
from automacao_novelis_desktop.desktop_app import main  # noqa: E402
from automacao_novelis_desktop.root_locator import find_project_root  # noqa: E402


def _force_reset_password(root: Path, argv: list[str]) -> None:
    if "-S" not in argv:
        print("Uso: run_app.py --force-reset-password -S <nova-senha>")
        sys.exit(1)
    index = argv.index("-S")
    if index + 1 >= len(argv):
        print("Informe a nova senha depois de -S.")
        sys.exit(1)
    new_password = argv[index + 1]
    if not new_password.strip():
        print("A nova senha nao pode ser vazia.")
        sys.exit(1)
    settings = load_settings(root)
    set_password(settings, new_password)
    save_settings(root, settings)
    print("Senha das configuracoes redefinida com sucesso.")


if __name__ == "__main__":
    project_root = find_project_root(START.parent)
    if "--force-reset-password" in sys.argv[1:]:
        _force_reset_password(project_root, sys.argv[1:])
    else:
        main(project_root)
