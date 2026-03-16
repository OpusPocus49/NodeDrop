from __future__ import annotations

import json
from enum import Enum
from typing import Any, Final


# ============================================================
# Protocol constants
# ============================================================

PROTOCOL_VERSION: Final[str] = "1.0"

MESSAGE_TYPE_FIELD: Final[str] = "type"
PROTOCOL_VERSION_FIELD: Final[str] = "protocol_version"

ITEM_TYPE_FILE: Final[str] = "FILE"
ITEM_TYPE_DIRECTORY: Final[str] = "DIRECTORY"
ALLOWED_ITEM_TYPES: Final[set[str]] = {ITEM_TYPE_FILE, ITEM_TYPE_DIRECTORY}


# ============================================================
# Message types
# ============================================================


class MessageType(str, Enum):
    """
    All supported NodeDrop V1 network message types.
    """

    NODE_ANNOUNCE = "NODE_ANNOUNCE"
    SESSION_REQUEST = "SESSION_REQUEST"
    SESSION_ACCEPTED = "SESSION_ACCEPTED"
    SESSION_REJECTED = "SESSION_REJECTED"
    AUTH_REQUEST = "AUTH_REQUEST"
    AUTH_RESPONSE = "AUTH_RESPONSE"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILED = "AUTH_FAILED"
    TRANSFER_INIT = "TRANSFER_INIT"
    FILE_INFO = "FILE_INFO"
    FILE_CHUNK = "FILE_CHUNK"
    FILE_COMPLETE = "FILE_COMPLETE"
    TRANSFER_COMPLETE = "TRANSFER_COMPLETE"
    TRANSFER_ACK = "TRANSFER_ACK"
    TRANSFER_ERROR = "TRANSFER_ERROR"
    TRANSFER_CANCEL = "TRANSFER_CANCEL"
    SESSION_CLOSE = "SESSION_CLOSE"


KNOWN_MESSAGE_TYPES: Final[set[str]] = {message_type.value for message_type in MessageType}


# ============================================================
# Required fields by message type
# ============================================================

REQUIRED_FIELDS_BY_TYPE: Final[dict[str, set[str]]] = {
    MessageType.NODE_ANNOUNCE.value: {
        "node_id",
        "display_name",
        "host_name",
        "ip_address",
        "tcp_port",
        "version",
    },
    MessageType.SESSION_REQUEST.value: {
        "session_id",
        "sender_id",
        "sender_name",
    },
    MessageType.SESSION_ACCEPTED.value: {
        "session_id",
    },
    MessageType.SESSION_REJECTED.value: {
        "session_id",
        "reason",
    },
    MessageType.AUTH_REQUEST.value: {
        "session_id",
    },
    MessageType.AUTH_RESPONSE.value: {
        "session_id",
        "password",
    },
    MessageType.AUTH_SUCCESS.value: {
        "session_id",
    },
    MessageType.AUTH_FAILED.value: {
        "session_id",
        "reason",
    },
    MessageType.TRANSFER_INIT.value: {
        "session_id",
        "job_id",
        "item_count",
        "total_bytes",
    },
    MessageType.FILE_INFO.value: {
        "session_id",
        "job_id",
        "relative_path",
        "item_type",
        "size_bytes",
        "checksum",
    },
    MessageType.FILE_CHUNK.value: {
        "session_id",
        "job_id",
        "relative_path",
        "chunk_size",
    },
    MessageType.FILE_COMPLETE.value: {
        "session_id",
        "job_id",
        "relative_path",
    },
    MessageType.TRANSFER_COMPLETE.value: {
        "session_id",
        "job_id",
    },
    MessageType.TRANSFER_ACK.value: {
        "session_id",
        "job_id",
    },
    MessageType.TRANSFER_ERROR.value: {
        "session_id",
        "job_id",
        "error_message",
    },
    MessageType.TRANSFER_CANCEL.value: {
        "session_id",
        "job_id",
        "reason",
    },
    MessageType.SESSION_CLOSE.value: {
        "session_id",
    },
}


# ============================================================
# Exceptions
# ============================================================


class ProtocolError(Exception):
    """
    Base exception for protocol-related errors.
    """


class MessageValidationError(ProtocolError):
    """
    Raised when a message is invalid.
    """


class MessageSerializationError(ProtocolError):
    """
    Raised when JSON serialization or deserialization fails.
    """


# ============================================================
# Internal helpers
# ============================================================


def _is_int_but_not_bool(value: Any) -> bool:
    """
    Return True only for genuine integers, excluding booleans.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    """
    Validate a non-empty string field and return its stripped value.
    """
    if not isinstance(value, str):
        raise MessageValidationError(f"Field '{field_name}' must be a string.")

    normalized = value.strip()
    if not normalized:
        raise MessageValidationError(f"Field '{field_name}' cannot be empty.")

    return normalized


def _ensure_message_is_dict(message: Any) -> dict[str, Any]:
    """
    Ensure the provided object is a dictionary.
    """
    if not isinstance(message, dict):
        raise MessageValidationError("Message must be a dictionary.")

    return dict(message)


# ============================================================
# Type helpers
# ============================================================


def normalize_message_type(message_type: str | MessageType) -> str:
    """
    Normalize a message type to its canonical string representation.
    """
    if isinstance(message_type, MessageType):
        return message_type.value

    if not isinstance(message_type, str):
        raise MessageValidationError("Message type must be a string or MessageType enum.")

    normalized = message_type.strip().upper()
    if not normalized:
        raise MessageValidationError("Message type cannot be empty.")

    return normalized


def is_known_message_type(message_type: str | MessageType) -> bool:
    """
    Return True if the provided message type is supported by the protocol.
    """
    try:
        normalized = normalize_message_type(message_type)
    except MessageValidationError:
        return False

    return normalized in KNOWN_MESSAGE_TYPES


def get_required_fields(message_type: str | MessageType) -> set[str]:
    """
    Return the required fields for a given message type.
    """
    normalized = normalize_message_type(message_type)

    if normalized not in KNOWN_MESSAGE_TYPES:
        raise MessageValidationError(f"Unknown message type: '{normalized}'")

    return set(REQUIRED_FIELDS_BY_TYPE.get(normalized, set()))


# ============================================================
# Message creation
# ============================================================


def create_message(message_type: str | MessageType, **fields: Any) -> dict[str, Any]:
    """
    Build a protocol message as a plain Python dictionary.

    The returned message is normalized and validated before being returned.
    """
    message: dict[str, Any] = {
        MESSAGE_TYPE_FIELD: normalize_message_type(message_type),
        PROTOCOL_VERSION_FIELD: PROTOCOL_VERSION,
    }
    message.update(fields)

    return validate_message(message)


# ============================================================
# Validation helpers
# ============================================================


def _validate_and_normalize_message_type(message: dict[str, Any]) -> str:
    """
    Validate and normalize the message type field.
    """
    if MESSAGE_TYPE_FIELD not in message:
        raise MessageValidationError("Missing required field: 'type'")

    raw_type = message[MESSAGE_TYPE_FIELD]
    if not isinstance(raw_type, str):
        raise MessageValidationError("Field 'type' must be a string.")

    normalized_type = normalize_message_type(raw_type)

    if normalized_type not in KNOWN_MESSAGE_TYPES:
        raise MessageValidationError(f"Unknown message type: '{normalized_type}'")

    message[MESSAGE_TYPE_FIELD] = normalized_type
    return normalized_type


def _validate_protocol_version(message: dict[str, Any]) -> None:
    """
    Validate protocol version if present.
    """
    if PROTOCOL_VERSION_FIELD not in message:
        return

    protocol_version = message[PROTOCOL_VERSION_FIELD]
    if not isinstance(protocol_version, str):
        raise MessageValidationError("Field 'protocol_version' must be a string.")

    if protocol_version.strip() != PROTOCOL_VERSION:
        raise MessageValidationError(
            f"Unsupported protocol version: '{protocol_version}'"
        )


def _validate_required_fields(message: dict[str, Any], message_type: str) -> None:
    """
    Validate required fields for a specific message type.
    """
    required_fields = REQUIRED_FIELDS_BY_TYPE.get(message_type, set())
    missing_fields = [field_name for field_name in required_fields if field_name not in message]

    if missing_fields:
        missing_fields_str = ", ".join(sorted(missing_fields))
        raise MessageValidationError(
            f"Missing required field(s) for '{message_type}': {missing_fields_str}"
        )


def _validate_common_fields(message: dict[str, Any]) -> None:
    """
    Validate field types and normalize selected values.
    """
    if "node_id" in message:
        message["node_id"] = _require_non_empty_string(message["node_id"], "node_id")

    if "display_name" in message:
        message["display_name"] = _require_non_empty_string(
            message["display_name"], "display_name"
        )

    if "host_name" in message:
        message["host_name"] = _require_non_empty_string(message["host_name"], "host_name")

    if "ip_address" in message:
        message["ip_address"] = _require_non_empty_string(
            message["ip_address"], "ip_address"
        )

    if "version" in message:
        message["version"] = _require_non_empty_string(message["version"], "version")

    if "session_id" in message:
        message["session_id"] = _require_non_empty_string(
            message["session_id"], "session_id"
        )

    if "job_id" in message:
        message["job_id"] = _require_non_empty_string(message["job_id"], "job_id")

    if "sender_id" in message:
        message["sender_id"] = _require_non_empty_string(message["sender_id"], "sender_id")

    if "sender_name" in message:
        message["sender_name"] = _require_non_empty_string(
            message["sender_name"], "sender_name"
        )

    if "password" in message:
        message["password"] = _require_non_empty_string(message["password"], "password")

    if "reason" in message:
        message["reason"] = _require_non_empty_string(message["reason"], "reason")

    if "error_message" in message:
        message["error_message"] = _require_non_empty_string(
            message["error_message"], "error_message"
        )

    if "checksum" in message:
        message["checksum"] = _require_non_empty_string(message["checksum"], "checksum")

    if "relative_path" in message:
        message["relative_path"] = _require_non_empty_string(
            message["relative_path"], "relative_path"
        )

    if "tcp_port" in message:
        tcp_port = message["tcp_port"]
        if not _is_int_but_not_bool(tcp_port):
            raise MessageValidationError("Field 'tcp_port' must be an integer.")
        if tcp_port < 1 or tcp_port > 65535:
            raise MessageValidationError("Field 'tcp_port' must be between 1 and 65535.")

    if "accepted" in message and not isinstance(message["accepted"], bool):
        raise MessageValidationError("Field 'accepted' must be a boolean.")

    if "item_count" in message:
        item_count = message["item_count"]
        if not _is_int_but_not_bool(item_count):
            raise MessageValidationError("Field 'item_count' must be an integer.")
        if item_count < 0:
            raise MessageValidationError("Field 'item_count' must be >= 0.")

    if "total_bytes" in message:
        total_bytes = message["total_bytes"]
        if not _is_int_but_not_bool(total_bytes):
            raise MessageValidationError("Field 'total_bytes' must be an integer.")
        if total_bytes < 0:
            raise MessageValidationError("Field 'total_bytes' must be >= 0.")

    if "size_bytes" in message:
        size_bytes = message["size_bytes"]
        if not _is_int_but_not_bool(size_bytes):
            raise MessageValidationError("Field 'size_bytes' must be an integer.")
        if size_bytes < 0:
            raise MessageValidationError("Field 'size_bytes' must be >= 0.")

    if "chunk_size" in message:
        chunk_size = message["chunk_size"]
        if not _is_int_but_not_bool(chunk_size):
            raise MessageValidationError("Field 'chunk_size' must be an integer.")
        if chunk_size < 0:
            raise MessageValidationError("Field 'chunk_size' must be >= 0.")

    if "item_type" in message:
        if not isinstance(message["item_type"], str):
            raise MessageValidationError("Field 'item_type' must be a string.")

        normalized_item_type = message["item_type"].strip().upper()
        if normalized_item_type not in ALLOWED_ITEM_TYPES:
            raise MessageValidationError(
                "Field 'item_type' must be 'FILE' or 'DIRECTORY'."
            )

        message["item_type"] = normalized_item_type


def validate_message(message: Any) -> dict[str, Any]:
    """
    Validate and normalize a protocol message.
    """
    validated_message = _ensure_message_is_dict(message)
    message_type = _validate_and_normalize_message_type(validated_message)
    _validate_protocol_version(validated_message)
    _validate_required_fields(validated_message, message_type)
    _validate_common_fields(validated_message)
    return validated_message


# ============================================================
# JSON serialization / deserialization
# ============================================================


def serialize_message(message: dict[str, Any]) -> str:
    """
    Validate and serialize a message to JSON.
    """
    normalized_message = validate_message(message)

    try:
        return json.dumps(normalized_message, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise MessageSerializationError(
            f"Failed to serialize message to JSON: {exc}"
        ) from exc


def deserialize_message(payload: str | bytes | bytearray) -> dict[str, Any]:
    """
    Deserialize JSON payload into a validated protocol message.
    """
    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MessageSerializationError(
                f"Failed to decode payload as UTF-8: {exc}"
            ) from exc

    if not isinstance(payload, str):
        raise MessageSerializationError("Payload must be a str, bytes, or bytearray.")

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise MessageSerializationError(f"Invalid JSON payload: {exc}") from exc

    return validate_message(parsed)


def parse_message(payload: str | bytes | bytearray) -> dict[str, Any]:
    """
    Convenience alias for deserialize_message().
    """
    return deserialize_message(payload)


# ============================================================
# Convenience helpers
# ============================================================


def message_has_type(message: Any, message_type: str | MessageType) -> bool:
    """
    Return True if a message is valid and matches the expected type.
    """
    try:
        validated_message = validate_message(message)
        expected_type = normalize_message_type(message_type)
        return validated_message[MESSAGE_TYPE_FIELD] == expected_type
    except MessageValidationError:
        return False