"""Byte-identical snapshot digest with cached JSON for immutable capital records."""
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import cached_property, lru_cache
import hashlib
import json

from .identity_history import IdentityHistory
from .snapshot import primitive


@lru_cache(maxsize=128)
def _schema(kind):
    return tuple((f.name, json.encoder.encode_basestring_ascii(f.name))
                 for f in sorted(fields(kind), key=lambda f: f.name))


class CapitalCanonical:
    """Only deeply immutable, validated capital records opt into object caching."""
    @cached_property
    def _capital_canonical_json(self):
        return _record(self)


def _record(value):
    return "{" + ",".join(key + ":" + _encoded(getattr(value, name))
                          for name, key in _schema(type(value))) + "}"


def _encoded(value):
    if isinstance(value, CapitalCanonical):
        return value._capital_canonical_json
    if isinstance(value, IdentityHistory):
        return json.dumps(value.record(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    if is_dataclass(value):
        return _record(value)
    if isinstance(value, Decimal):
        return json.encoder.encode_basestring_ascii(str(value))
    if isinstance(value, (datetime, date)):
        return json.encoder.encode_basestring_ascii(value.isoformat())
    if isinstance(value, Enum):
        return _encoded(value.value)
    if isinstance(value, str):
        return json.encoder.encode_basestring_ascii(value)
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, tuple):
        return "[" + ",".join(_encoded(item) for item in value) + "]"
    # Preserve the original codec behavior for dicts, lists and unsupported types.
    return json.dumps(primitive(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(_encoded(value).encode()).hexdigest()
