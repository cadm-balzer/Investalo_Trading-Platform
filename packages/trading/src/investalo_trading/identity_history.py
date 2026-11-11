"""Immutable, bounded, append-only identity membership with compact Merkle receipts."""
from dataclasses import dataclass, field
import hashlib
import json

VERSION = "research-identity-history/1"
MAX_CAPACITY = 100_000
EMPTY = hashlib.sha256(VERSION.encode()).hexdigest()
NAMESPACES = ("intent", "order", "fill", "event")


def _identifier(value):
    if not isinstance(value, str) or not value or len(value) > 128 or value.strip() != value:
        raise ValueError("bounded identity required")


def _height(node):
    return node.height if node is not None else 0


@dataclass(frozen=True)
class _Node:
    key: str
    left: "_Node | None" = None
    right: "_Node | None" = None
    height: int = field(init=False)
    count: int = field(init=False)
    first: str = field(init=False)
    last: str = field(init=False)
    head: str = field(init=False)

    def __post_init__(self):
        _identifier(self.key)
        if any(node is not None and not isinstance(node, _Node) for node in (self.left, self.right)):
            raise ValueError("immutable identity nodes required")
        if (self.left is not None and self.left.last >= self.key
                or self.right is not None and self.right.first <= self.key):
            raise ValueError("identity tree ordering violation")
        count = 1 + sum(node.count for node in (self.left, self.right) if node is not None)
        height = 1 + max(_height(self.left), _height(self.right))
        if count > MAX_CAPACITY or height > 32:
            raise ValueError("identity tree resource bound exceeded")
        object.__setattr__(self, "count", count)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "first", self.left.first if self.left is not None else self.key)
        object.__setattr__(self, "last", self.right.last if self.right is not None else self.key)
        body = [VERSION, self.key, count, height,
                self.left.head if self.left is not None else EMPTY,
                self.right.head if self.right is not None else EMPTY]
        object.__setattr__(self, "head", hashlib.sha256(json.dumps(
            body, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest())


def _left(node):
    right = node.right
    return _Node(right.key, _Node(node.key, node.left, right.left), right.right)


def _right(node):
    left = node.left
    return _Node(left.key, left.left, _Node(node.key, left.right, node.right))


def _insert(node, key):
    if node is None:
        return _Node(key)
    if key == node.key:
        raise ValueError("duplicate evidence identity")
    if key < node.key:
        node = _Node(node.key, _insert(node.left, key), node.right)
    else:
        node = _Node(node.key, node.left, _insert(node.right, key))
    balance = _height(node.left) - _height(node.right)
    if balance > 1:
        if key > node.left.key:
            node = _Node(node.key, _left(node.left), node.right)
        return _right(node)
    if balance < -1:
        if key < node.right.key:
            node = _Node(node.key, node.left, _right(node.right))
        return _left(node)
    return node


@dataclass(frozen=True)
class IdentityHistory:
    """Root receipts bind all retained IDs; receipts alone cannot restore membership."""
    namespace: str
    capacity: int = 50_000
    _root: _Node | None = field(default=None, repr=False)

    def __post_init__(self):
        if self.namespace not in NAMESPACES or type(self.capacity) is not int or not 1 <= self.capacity <= MAX_CAPACITY:
            raise ValueError("explicit bounded identity policy required")
        if self._root is not None and not isinstance(self._root, _Node):
            raise ValueError("immutable identity root required")
        if len(self) > self.capacity:
            raise ValueError("identity capacity exhausted; never evict evidence")

    def __len__(self):
        return self._root.count if self._root is not None else 0

    def __contains__(self, value):
        _identifier(value)
        node = self._root
        while node is not None:
            if value == node.key:
                return True
            node = node.left if value < node.key else node.right
        return False

    def append(self, value):
        _identifier(value)
        if value in self:
            raise ValueError("duplicate evidence identity")
        if len(self) >= self.capacity:
            raise ValueError("identity capacity exhausted; never evict evidence")
        return IdentityHistory(self.namespace, self.capacity, _insert(self._root, value))

    def record(self):
        return {"schema_version": VERSION, "namespace": self.namespace, "capacity": self.capacity,
                "count": len(self), "root_digest": self._root.head if self._root is not None else EMPTY}
