"""Authorization status reported by Rodopar, including older cached SQL rows."""


def authorization_status(row):
    value = row.get("CTEAUT")
    if value is None or not str(value).strip():
        value = (row.get("__sql") or {}).get("CTEAUT")
    return str(value or "").strip().upper()
