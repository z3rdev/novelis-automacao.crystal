"""Audit executable MSI standard actions, not only the presence of merged tables."""

REQUIRED_ACTIONS = (
    "InstallInitialize", "InstallFiles", "WriteRegistryValues", "SelfRegModules",
    "SelfUnregModules", "RemoveRegistryValues", "RemoveFiles", "RemoveFolders",
    "CreateFolders", "PublishComponents", "UnpublishComponents", "InstallFinalize",
)


def verify_execute_sequence(rows):
    actions = {name: (condition, int(number or 0)) for name, condition, number in rows}
    missing = [name for name in REQUIRED_ACTIONS
               if name not in actions or actions[name][1] <= 0
               or actions[name][0].strip().upper() in {"0", "FALSE"}]
    if missing:
        raise ValueError("MSI sem acao executavel obrigatoria: " + ", ".join(missing))
    order = {name: actions[name][1] for name in REQUIRED_ACTIONS}
    chains = (
        ("InstallInitialize", "InstallFiles", "WriteRegistryValues", "SelfRegModules", "InstallFinalize"),
        ("InstallInitialize", "SelfUnregModules", "RemoveFiles", "InstallFinalize"),
        ("InstallInitialize", "RemoveRegistryValues", "WriteRegistryValues", "InstallFinalize"),
        ("InstallInitialize", "RemoveFiles", "RemoveFolders", "CreateFolders", "InstallFiles"),
        ("InstallInitialize", "UnpublishComponents", "PublishComponents", "InstallFinalize"),
    )
    if any(not all(order[a] < order[b] for a, b in zip(chain, chain[1:])) for chain in chains):
        raise ValueError("Ordem das acoes MSI de instalacao/registro/remocao incorreta.")
    return order
