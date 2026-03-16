from __future__ import annotations

import sys
from pathlib import Path

# ajoute src au PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

from network.protocol import (
    MessageSerializationError,
    MessageType,
    MessageValidationError,
    create_message,
    deserialize_message,
    is_known_message_type,
    message_has_type,
    serialize_message,
    validate_message,
)


def test_create_valid_node_announce() -> None:
    message = create_message(
        MessageType.NODE_ANNOUNCE,
        node_id="node-123",
        display_name="Alex-PC",
        host_name="DESKTOP-ALEX",
        ip_address="192.168.1.10",
        tcp_port=48556,
        version="1.0.0-dev",
    )

    assert message["type"] == "NODE_ANNOUNCE"
    assert message["protocol_version"] == "1.0"
    assert message["node_id"] == "node-123"


def test_validate_valid_session_request() -> None:
    message = {
        "type": "SESSION_REQUEST",
        "protocol_version": "1.0",
        "session_id": "sess-001",
        "sender_id": "node-123",
        "sender_name": "Alex-PC",
    }

    validated = validate_message(message)
    assert validated["type"] == "SESSION_REQUEST"


def test_serialize_and_deserialize() -> None:
    original = create_message(
        MessageType.SESSION_ACCEPTED,
        session_id="sess-001",
    )

    payload = serialize_message(original)
    restored = deserialize_message(payload)

    assert restored == original


def test_message_type_helpers() -> None:
    assert is_known_message_type("NODE_ANNOUNCE") is True
    assert is_known_message_type("UNKNOWN_TYPE") is False

    message = create_message(
        MessageType.AUTH_SUCCESS,
        session_id="sess-001",
    )

    assert message_has_type(message, MessageType.AUTH_SUCCESS) is True
    assert message_has_type(message, MessageType.AUTH_FAILED) is False


def test_missing_required_field() -> None:
    invalid_message = {
        "type": "SESSION_ACCEPTED",
        "protocol_version": "1.0",
    }

    try:
        validate_message(invalid_message)
    except MessageValidationError:
        return

    raise AssertionError("Expected MessageValidationError was not raised.")


def test_unknown_message_type() -> None:
    invalid_message = {
        "type": "DOES_NOT_EXIST",
        "protocol_version": "1.0",
    }

    try:
        validate_message(invalid_message)
    except MessageValidationError:
        return

    raise AssertionError("Expected MessageValidationError was not raised.")


def test_invalid_json_payload() -> None:
    invalid_payload = '{"type": "SESSION_CLOSE", "session_id": "abc"'

    try:
        deserialize_message(invalid_payload)
    except MessageSerializationError:
        return

    raise AssertionError("Expected MessageSerializationError was not raised.")


def run_all_tests() -> None:
    tests = [
        test_create_valid_node_announce,
        test_validate_valid_session_request,
        test_serialize_and_deserialize,
        test_message_type_helpers,
        test_missing_required_field,
        test_unknown_message_type,
        test_invalid_json_payload,
        test_message_type_is_normalized,
        test_item_type_is_normalized,
        test_invalid_protocol_version,
        test_bool_is_rejected_for_integer_fields,   
    ]

    passed = 0

    for test_func in tests:
        test_name = test_func.__name__
        try:
            test_func()
            print(f"[OK] {test_name}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test_name} -> {exc}")

    print()
    print(f"Résultat : {passed}/{len(tests)} tests réussis.")

    if passed != len(tests):
        raise SystemExit(1)
    
def test_message_type_is_normalized() -> None:
    message = {
        "type": "node_announce",
        "protocol_version": "1.0",
        "node_id": "node-123",
        "display_name": "Alex-PC",
        "host_name": "DESKTOP-ALEX",
        "ip_address": "192.168.1.10",
        "tcp_port": 48556,
        "version": "1.0.0-dev",
    }

    validated = validate_message(message)
    assert validated["type"] == "NODE_ANNOUNCE"


def test_item_type_is_normalized() -> None:
    message = {
        "type": "FILE_INFO",
        "protocol_version": "1.0",
        "session_id": "sess-001",
        "job_id": "job-001",
        "relative_path": "docs/test.txt",
        "item_type": "file",
        "size_bytes": 1234,
    }

    validated = validate_message(message)
    assert validated["item_type"] == "FILE"


def test_invalid_protocol_version() -> None:
    invalid_message = {
        "type": "SESSION_CLOSE",
        "protocol_version": "2.0",
        "session_id": "sess-001",
    }

    try:
        validate_message(invalid_message)
    except MessageValidationError:
        return

    raise AssertionError("Expected MessageValidationError was not raised.")


def test_bool_is_rejected_for_integer_fields() -> None:
    invalid_message = {
        "type": "NODE_ANNOUNCE",
        "protocol_version": "1.0",
        "node_id": "node-123",
        "display_name": "Alex-PC",
        "host_name": "DESKTOP-ALEX",
        "ip_address": "192.168.1.10",
        "tcp_port": True,
        "version": "1.0.0-dev",
    }

    try:
        validate_message(invalid_message)
    except MessageValidationError:
        return

    raise AssertionError("Expected MessageValidationError was not raised.")


if __name__ == "__main__":
    run_all_tests()