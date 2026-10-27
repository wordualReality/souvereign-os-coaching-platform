"""Public-domain Ed25519 for local synthetic proofs. Not a live trust anchor.

Math follows the SUPERCOP python reference. This module exists because the
KDB CI image has no cryptography extra. It does not admit a production issuer.
"""
from __future__ import annotations

import hashlib

B = 256
Q = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493


def _expmod(base: int, exp: int, mod: int) -> int:
    result = 1
    base %= mod
    while exp:
        if exp & 1:
            result = (result * base) % mod
        base = (base * base) % mod
        exp >>= 1
    return result


def _inv(x: int) -> int:
    return _expmod(x, Q - 2, Q)


D = -121665 * _inv(121666) % Q
I = _expmod(2, (Q - 1) // 4, Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(D * y * y + 1)
    x = _expmod(xx, (Q + 3) // 8, Q)
    if (x * x - xx) % Q != 0:
        x = (x * I) % Q
    if x % 2 != 0:
        x = Q - x
    return x


BY = 4 * _inv(5)
BX = _xrecover(BY)
BP = (BX % Q, BY % Q)


def _edwards(p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - D * x1 * x2 * y1 * y2)
    return (x3 % Q, y3 % Q)


def _scalarmult(point: tuple[int, int], e: int) -> tuple[int, int]:
    q = (0, 1)
    p = point
    while e:
        if e & 1:
            q = _edwards(q, p)
        p = _edwards(p, p)
        e >>= 1
    return q


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _encodeint(y: int) -> bytes:
    bits = [(y >> i) & 1 for i in range(B)]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(B // 8))


def _encodepoint(p: tuple[int, int]) -> bytes:
    x, y = p
    bits = [(y >> i) & 1 for i in range(B - 1)] + [x & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(B // 8))


def _decodeint(s: bytes) -> int:
    return sum(2**i * _bit(s, i) for i in range(B))


def _isoncurve(p: tuple[int, int]) -> bool:
    x, y = p
    return (-x * x + y * y - 1 - D * x * x * y * y) % Q == 0


def _decodepoint(s: bytes) -> tuple[int, int]:
    y = sum(2**i * _bit(s, i) for i in range(B - 1))
    x = _xrecover(y)
    if x & 1 != _bit(s, B - 1):
        x = Q - x
    point = (x, y)
    if not _isoncurve(point):
        raise ValueError("point not on curve")
    return point


def _hint(m: bytes) -> int:
    h = hashlib.sha512(m).digest()
    return sum(2**i * _bit(h, i) for i in range(2 * B))


def publickey(sk: bytes) -> bytes:
    if len(sk) != 32:
        raise ValueError("seed must be 32 bytes")
    h = hashlib.sha512(sk).digest()
    a = 2 ** (B - 2) + sum(2**i * _bit(h, i) for i in range(3, B - 2))
    return _encodepoint(_scalarmult(BP, a))


def signature(message: bytes, sk: bytes, pk: bytes) -> bytes:
    h = hashlib.sha512(sk).digest()
    a = 2 ** (B - 2) + sum(2**i * _bit(h, i) for i in range(3, B - 2))
    r = _hint(bytes(h[i] for i in range(B // 8, B // 4)) + message)
    r_point = _scalarmult(BP, r)
    s = (r + _hint(_encodepoint(r_point) + pk + message) * a) % L
    return _encodepoint(r_point) + _encodeint(s)


def verify(sig: bytes, message: bytes, pk: bytes) -> bool:
    if len(sig) != 64 or len(pk) != 32:
        return False
    try:
        r = _decodepoint(sig[:32])
        a = _decodepoint(pk)
    except ValueError:
        return False
    s = _decodeint(sig[32:])
    if s >= L:
        return False
    h = _hint(_encodepoint(r) + pk + message)
    return _scalarmult(BP, s) == _edwards(r, _scalarmult(a, h))
