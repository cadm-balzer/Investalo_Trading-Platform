"""Explicit JSON snapshot codec; no pickle or executable deserialization."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Union, get_args, get_origin, get_type_hints
import types

from . import models

SCHEMA_VERSION = 1


def primitive(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {f.name: primitive(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [primitive(v) for v in value]
    return value


def digest(value: Any) -> str:
    raw = json.dumps(primitive(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def dumps(state: models.EngineState) -> str:
    return json.dumps({"schema_version": SCHEMA_VERSION, "state": primitive(state)},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def _decode(kind: Any, value: Any) -> Any:
    if value is None:
        if type(None) not in get_args(kind):
            raise ValueError("unexpected null")
        return None
    origin = get_origin(kind)
    if origin in (Union, types.UnionType):
        return _decode(next(k for k in get_args(kind) if k is not type(None)), value)
    if origin is tuple:
        args = get_args(kind)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(args[0], v) for v in value)
        if len(value) != len(args):
            raise ValueError("invalid tuple length")
        return tuple(_decode(k, v) for k, v in zip(args, value))
    if kind is Decimal:
        if not isinstance(value, str):
            raise ValueError("money must be encoded as decimal strings")
        result = Decimal(value)
        if not result.is_finite():
            raise ValueError("nonfinite money")
        return result
    if kind is datetime:
        return models.utc(datetime.fromisoformat(value))
    if kind is date:
        return date.fromisoformat(value)
    if isinstance(kind, type) and issubclass(kind, Enum):
        return kind(value)
    if dataclasses.is_dataclass(kind):
        fields = {f.name for f in dataclasses.fields(kind)}
        if set(value) != fields:
            raise ValueError("snapshot record fields differ from schema")
        hints = get_type_hints(kind)
        return kind(**{name: _decode(hints[name], item) for name, item in value.items()})
    if kind is bool and type(value) is not bool:
        raise ValueError("invalid boolean")
    if kind is int and type(value) is not int:
        raise ValueError("invalid integer")
    if kind is str and not isinstance(value, str):
        raise ValueError("invalid string")
    return value


def loads(payload: str) -> models.EngineState:
    document = json.loads(payload)
    if set(document) != {"schema_version", "state"} or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported snapshot schema")
    state = _decode(models.EngineState, document["state"])
    if state.version != models.VERSION:
        raise ValueError("unsupported strategy snapshot")
    return state
