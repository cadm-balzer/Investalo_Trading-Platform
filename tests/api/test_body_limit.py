import asyncio

from investalo_api.body_limit import BodyLimitMiddleware


def exercise(chunks, limit):
    received = []
    sent = []
    queue = [{"type": "http.request", "body": chunk, "more_body": i < len(chunks)-1}
             for i, chunk in enumerate(chunks)]

    async def receive():
        return queue.pop(0)

    async def send(message):
        sent.append(message)

    async def inner(scope, receive, send):
        received.append(await receive())

    asyncio.run(BodyLimitMiddleware(inner, limit)({"type": "http"}, receive, send))
    return received, sent


def test_chunked_oversize_is_rejected_before_framework_receives_body():
    received, sent = exercise([b"12345678", b"901"], 10)
    assert received == []
    assert sent[0]["status"] == 413
    assert b"12345678" not in sent[1]["body"]


def test_bounded_chunks_preserve_exact_signature_bytes():
    received, sent = exercise([b"\x00abc", b"\xffdef"], 8)
    assert sent == []
    assert received == [{"type": "http.request", "body": b"\x00abc\xffdef", "more_body": False}]
