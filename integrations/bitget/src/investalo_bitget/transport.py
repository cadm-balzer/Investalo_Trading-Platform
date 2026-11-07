"""Opt-in HTTPS transport: fixed requests, CA/hostname verification, no proxies."""
from dataclasses import dataclass
import ssl
from typing import Callable
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from .models import BitgetRejected, ErrorCode
from .signing import SignedReadRequest

MAX_RESPONSE_BYTES = 1024 * 1024


@dataclass(frozen=True, repr=False)
class ReadResponse:
    status: int
    body: bytes


Transport = Callable[[SignedReadRequest], ReadResponse]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BitgetRejected(ErrorCode.REDIRECT_DENIED)


@dataclass(frozen=True)
class HTTPSReadTransport:
    """Explicit selection requires an IP-gated binding in ClassicReadClient."""
    timeout_seconds: float = 10

    def __post_init__(self):
        if not isinstance(self.timeout_seconds, (float, int)) or not 1 <= self.timeout_seconds <= 20:
            raise BitgetRejected(ErrorCode.INVALID_REQUEST)

    def __call__(self, request: SignedReadRequest) -> ReadResponse:
        if not isinstance(request, SignedReadRequest):
            raise BitgetRejected(ErrorCode.INVALID_REQUEST)
        request.validate()
        try:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            # Ignore HTTP(S)_PROXY and environment proxy credentials entirely.
            opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), _NoRedirect())
            outgoing = Request(request.url, headers=dict(request.headers), method="GET")
            with opener.open(outgoing, timeout=self.timeout_seconds) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise BitgetRejected(ErrorCode.RESPONSE_TOO_LARGE)
                if response.status != 200:
                    raise BitgetRejected(ErrorCode.HTTP_FAILURE)
                return ReadResponse(response.status, body)
        except BitgetRejected:
            raise
        except HTTPError as error:
            # HTTPError owns a response handle; close it before its finalizer
            # could emit a ResourceWarning containing the provider's raw reason.
            try:
                error.close()
            except Exception:
                pass
            raise BitgetRejected(ErrorCode.HTTP_FAILURE) from None
        except Exception:
            # urllib/SSL errors can retain request/auth data. Suppress their chain.
            raise BitgetRejected(ErrorCode.TRANSPORT_FAILURE) from None
