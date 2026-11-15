import asyncio

from fastapi import HTTPException, Request


async def require_operator_session(request: Request) -> dict:
    audit = getattr(request.app.state, "session_audit", None)
    identifier = request.headers.get("X-Operator-Session")
    session = await asyncio.to_thread(audit.session, identifier) if audit and identifier else None
    if not session:
        raise HTTPException(401, "Entre no Cargo Hub para continuar.")
    return session
