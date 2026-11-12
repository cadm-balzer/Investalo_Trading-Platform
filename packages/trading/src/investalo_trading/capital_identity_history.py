"""Separate larger retained-ID policy for hourly capital research; no eviction."""
from dataclasses import dataclass
import hashlib
import json

from .identity_history import IdentityHistory, NAMESPACES, _Node, _height, _identifier

VERSION = "capital-research-identity-history/1"
MAX_CAPACITY = 1_000_000
EMPTY = hashlib.sha256(VERSION.encode()).hexdigest()


@dataclass(frozen=True)
class _CapitalNode(_Node):
    def __post_init__(self):
        _identifier(self.key)
        if any(n is not None and type(n) is not _CapitalNode for n in (self.left, self.right)):
            raise ValueError("own immutable capital identity nodes required")
        if (self.left is not None and self.left.last >= self.key
                or self.right is not None and self.right.first <= self.key):
            raise ValueError("capital identity tree ordering violation")
        count = 1 + sum(n.count for n in (self.left, self.right) if n is not None)
        height = 1 + max(_height(self.left), _height(self.right))
        if count > MAX_CAPACITY or height > 32:
            raise ValueError("capital identity tree resource bound exceeded")
        for name, value in (
            ("count", count), ("height", height),
            ("first", self.left.first if self.left is not None else self.key),
            ("last", self.right.last if self.right is not None else self.key),
        ):
            object.__setattr__(self, name, value)
        body = [VERSION, self.key, count, height,
                self.left.head if self.left is not None else EMPTY,
                self.right.head if self.right is not None else EMPTY]
        object.__setattr__(self, "head", hashlib.sha256(json.dumps(
            body, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest())


def _left(node):
    right = node.right
    return _CapitalNode(right.key, _CapitalNode(node.key, node.left, right.left), right.right)


def _right(node):
    left = node.left
    return _CapitalNode(left.key, left.left, _CapitalNode(node.key, left.right, node.right))


def _insert(node, key):
    if node is None:
        return _CapitalNode(key)
    if key == node.key:
        raise ValueError("duplicate capital evidence identity")
    if key < node.key:
        node = _CapitalNode(node.key, _insert(node.left, key), node.right)
    else:
        node = _CapitalNode(node.key, node.left, _insert(node.right, key))
    balance = _height(node.left) - _height(node.right)
    if balance > 1:
        if key > node.left.key:
            node = _CapitalNode(node.key, _left(node.left), node.right)
        return _right(node)
    if balance < -1:
        if key < node.right.key:
            node = _CapitalNode(node.key, node.left, _right(node.right))
        return _left(node)
    return node


@dataclass(frozen=True)
class CapitalIdentityHistory(IdentityHistory):
    """Compatible membership interface, distinct bounded policy and hash domain."""
    capacity: int = 250_000

    def __post_init__(self):
        if (self.namespace not in NAMESPACES or type(self.capacity) is not int
                or not 1 <= self.capacity <= MAX_CAPACITY):
            raise ValueError("explicit bounded capital identity policy required")
        if self._root is not None and type(self._root) is not _CapitalNode:
            raise ValueError("own immutable capital identity root required")
        if len(self) > self.capacity:
            raise ValueError("capital identity capacity exhausted; never evict evidence")

    def append(self, value):
        _identifier(value)
        if value in self:
            raise ValueError("duplicate capital evidence identity")
        if len(self) >= self.capacity:
            raise ValueError("capital identity capacity exhausted; never evict evidence")
        return CapitalIdentityHistory(self.namespace, self.capacity, _insert(self._root, value))

    def record(self):
        return {"schema_version": VERSION, "namespace": self.namespace, "capacity": self.capacity,
                "count": len(self), "root_digest": self._root.head if self._root is not None else EMPTY}
