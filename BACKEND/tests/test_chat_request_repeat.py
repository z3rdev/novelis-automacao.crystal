import os
from uuid import uuid4

import pytest
from test_chat_postgres import chat, create, sample_pdf  # noqa: F401 - isolated PostgreSQL fixture

from app.domain.chat import ChatConflict, GnreRequestInput

pytestmark = pytest.mark.skipif(
    os.getenv("NOVELIS_CHAT_PG_TEST") != "1", reason="Isolated PostgreSQL test is opt-in"
)


@pytest.mark.parametrize("files", [(), ("guia",), ("comprovante",), ("guia", "comprovante")])
def test_resend_keeps_saved_documents_status_and_assignee(chat, files):  # noqa: F811
    owner, financial, room = create(chat)
    cte = f"777-10-{uuid4().int % 1000000000}"
    original = chat.request(owner, room, GnreRequestInput(cte=cte, note="Documentos solicitados"))
    chat.claim(financial, room, original["id"])
    for kind in files:
        chat.upload(financial, room, original["id"], kind, uuid4(), f"{kind}.pdf", sample_pdf(100))
    saved = chat.detail(owner, room)["requests"][0]

    resend = GnreRequestInput(cte=cte)
    assert chat.request(owner, room, resend)["id"] == original["id"]
    assert chat.request(owner, room, resend)["id"] == original["id"]

    detail = chat.detail(owner, room)
    assert detail["requests"] == [saved]
    cards = [message for message in detail["messages"] if message["kind"] == "request"]
    assert len(cards) == 2
    assert all(message["request_id"] == original["id"] for message in cards)
    assert cards[-1]["client_id"] == str(resend.client_id)
    with chat.store.connection() as db:
        assert (
            db.execute(
                "SELECT count(*) AS total FROM public.cargo_hub_chat_requests WHERE room_id=%s AND cte=%s",
                (room, cte),
            ).fetchone()["total"]
            == 1
        )
    for kind in files:
        assert chat.download(owner, room, original["id"], kind)[0] == sample_pdf(100)


def test_resend_token_cannot_create_another_cte_request(chat):  # noqa: F811
    owner, _financial, room = create(chat)
    first = GnreRequestInput(cte="777-10-1")
    chat.request(owner, room, first)
    with pytest.raises(ChatConflict):
        chat.request(owner, room, GnreRequestInput(cte="777-10-2", client_id=first.client_id))
    detail = chat.detail(owner, room)
    assert len(detail["messages"]) == 1
    assert [request["cte"] for request in detail["requests"]] == [first.cte]
