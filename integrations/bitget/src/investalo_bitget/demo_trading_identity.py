"""Classic Demo trading-key identity policy. Parses replies; never places orders."""
from . import parse
from .models import READ_AUTHORITIES, BitgetRejected, ClassicIdentity, ErrorCode, address, uid

REQUIRED = frozenset(("coow", "cpow", "stow"))
ALLOWED = REQUIRED | READ_AUTHORITIES


def authorities(values, *, canonical=False):
    if (type(values) not in (list, tuple) or not 3 <= len(values) <= len(ALLOWED)
            or any(type(value) is not str or value not in ALLOWED for value in values)
            or len(set(values)) != len(values) or not REQUIRED <= set(values)
            or canonical and tuple(values) != tuple(sorted(values))):
        raise BitgetRejected(ErrorCode.PERMISSION_REJECTED)
    return tuple(sorted(values))


def trading_identity(response):
    """Separate from parse.identity: writable keys remain rejected there."""
    raw, at = parse.envelope(response)
    if (type(raw) is not dict or not {"userId", "authorities"} <= raw.keys()
            or {"permType", "permissions", "uid", "accountMode", "accountType"} & raw.keys()):
        raise BitgetRejected(ErrorCode.MODE_UNSUPPORTED)
    rights = authorities(raw["authorities"])
    user_id = uid(raw["userId"])
    parent = None if raw.get("parentId") is None else uid(raw["parentId"], parent=True)
    ips = raw.get("ips")
    whitelist = None
    if ips is not None:
        if type(ips) is not str or len(ips) > 2048:
            raise BitgetRejected(ErrorCode.IP_MISMATCH)
        parts = ips.split(",") if ips else []
        if len(parts) > 32 or any(not value.strip() for value in parts):
            raise BitgetRejected(ErrorCode.IP_MISMATCH)
        whitelist = tuple(address(value.strip()) for value in parts)
        if len(set(whitelist)) != len(whitelist):
            raise BitgetRejected(ErrorCode.IP_MISMATCH)
    return ClassicIdentity(user_id, parent, rights, whitelist, at)
