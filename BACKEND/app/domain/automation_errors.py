class AutomationBusyError(RuntimeError):
    """Another automation owns this backend's execution slot."""
