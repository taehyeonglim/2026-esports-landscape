"""Pre-persistence sanitizers for untrusted external values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Mapping
from urllib.parse import urlsplit



class SanitizationError(ValueError):
    """Base exception for values that cannot safely be persisted."""


class UnsupportedFieldError(SanitizationError):
    """Raised when a record contains a key outside the typed allowlist."""


class InvalidExternalValueError(SanitizationError):
    """Raised when an allowlisted field has the wrong type or shape."""


class ErrorKind(str, Enum):
    """Safe categories for persisted exception records."""

    VALIDATION = "validation"
    NETWORK = "network"
    PARSE = "parse"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SanitizedUrl:
    """A URL reduced to its non-identifying scheme and host."""

    scheme: str
    host: str
    path_digest: str | None

    @property
    def value(self) -> str:
        """Return the safe URL representation for storage."""

        return f"{self.scheme}://{self.host}"


@dataclass(frozen=True, slots=True)
class SanitizedException:
    """A persistable exception category and opaque identifier."""

    kind: ErrorKind
    opaque_id: str


_ALLOWED_FIELDS = frozenset({"url", "title", "path", "locator", "exception"})


def _salt_bytes(salt: str | bytes) -> bytes:
    if isinstance(salt, str):
        salt = salt.encode("utf-8")
    if not isinstance(salt, bytes) or not salt:
        raise InvalidExternalValueError("salt must be a non-empty str or bytes")
    return salt


def salted_digest(value: str, *, salt: str | bytes) -> str:
    """Return a stable opaque digest without retaining the source value."""

    if not isinstance(value, str):
        raise InvalidExternalValueError("digest values must be strings")
    digest = hashlib.sha256()
    digest.update(_salt_bytes(salt))
    digest.update(b"\0")
    digest.update(value.encode("utf-8"))
    return digest.hexdigest()


_ALLOWED_PORTS = {"http": 80, "https": 443}

def sanitize_url(url: str, *, salt: str | bytes) -> SanitizedUrl:
    """Keep only scheme and host, replacing any path with a salted digest."""

    if not isinstance(url, str):
        raise InvalidExternalValueError("url must be a string")
    _salt_bytes(salt)
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_PORTS or not parsed.hostname:
        raise InvalidExternalValueError("url must be an absolute HTTP(S) URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise InvalidExternalValueError("url port is invalid") from exc
    if port is not None and port != _ALLOWED_PORTS[scheme]:
        raise InvalidExternalValueError("url port is not allowed")
    path_digest = salted_digest(parsed.path, salt=salt) if parsed.path else None
    return SanitizedUrl(parsed.scheme.lower(), parsed.hostname.lower(), path_digest)


def sanitize_exception(error: BaseException, *, salt: str | bytes) -> SanitizedException:
    """Convert an exception to a safe category and opaque identifier."""

    if not isinstance(error, BaseException):
        raise InvalidExternalValueError("exception must derive from BaseException")
    if isinstance(error, (SanitizationError, ValueError, TypeError)):
        kind = ErrorKind.VALIDATION
    elif isinstance(error, (ConnectionError, TimeoutError, OSError)):
        kind = ErrorKind.NETWORK
    elif isinstance(error, (UnicodeError, SyntaxError)):
        kind = ErrorKind.PARSE
    else:
        kind = ErrorKind.UNKNOWN
    identity = f"{type(error).__module__}.{type(error).__qualname__}"
    return SanitizedException(kind, salted_digest(identity, salt=salt))


def sanitize_external_values(
    values: Mapping[str, object], *, salt: str | bytes
) -> dict[str, str | SanitizedUrl | SanitizedException]:
    """Sanitize a typed allowlist of external fields before persistence."""

    unknown = set(values) - _ALLOWED_FIELDS
    if unknown:
        raise UnsupportedFieldError("unsupported_external_field")
    _salt_bytes(salt)

    result: dict[str, str | SanitizedUrl | SanitizedException] = {}
    for key, value in values.items():
        if key == "exception":
            if not isinstance(value, BaseException):
                raise InvalidExternalValueError("exception must derive from BaseException")
            result[key] = sanitize_exception(value, salt=salt)
        elif key == "url":
            result[key] = sanitize_url(_require_string(key, value), salt=salt)
        else:
            text = _require_string(key, value)
            result[key] = salted_digest(text, salt=salt)
    return result


def _require_string(key: str, value: object) -> str:
    if not isinstance(value, str):
        raise InvalidExternalValueError(f"{key} must be a string")
    return value
