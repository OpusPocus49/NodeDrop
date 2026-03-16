from __future__ import annotations

import pytest

from core.auth_manager import AuthManager, AuthResult


def test_auth_manager_accepts_valid_password() -> None:
    manager = AuthManager(shared_password="nodepass")

    result = manager.verify_password("nodepass")

    assert isinstance(result, AuthResult)
    assert result.success is True
    assert result.reason is None


def test_auth_manager_rejects_invalid_password() -> None:
    manager = AuthManager(shared_password="nodepass")

    result = manager.verify_password("wrongpass")

    assert result.success is False
    assert result.reason == "INVALID_PASSWORD"


def test_auth_manager_rejects_empty_received_password() -> None:
    manager = AuthManager(shared_password="nodepass")

    result = manager.verify_password("   ")

    assert result.success is False
    assert result.reason == "EMPTY_PASSWORD"


def test_auth_manager_strips_surrounding_whitespace_on_verification() -> None:
    manager = AuthManager(shared_password="nodepass")

    result = manager.verify_password("  nodepass   ")

    assert result.success is True
    assert result.reason is None


def test_auth_manager_password_comparison_is_case_sensitive() -> None:
    manager = AuthManager(shared_password="NodePass")

    result = manager.verify_password("nodepass")

    assert result.success is False
    assert result.reason == "INVALID_PASSWORD"


def test_auth_manager_rejects_empty_initial_password() -> None:
    with pytest.raises(ValueError, match="shared_password cannot be empty"):
        AuthManager(shared_password="   ")


def test_auth_manager_rejects_non_string_initial_password() -> None:
    with pytest.raises(TypeError, match="Password value must be a string"):
        AuthManager(shared_password=12345)  # type: ignore[arg-type]


def test_update_password_replaces_existing_password() -> None:
    manager = AuthManager(shared_password="oldpass")

    manager.update_password("newpass")

    old_result = manager.verify_password("oldpass")
    new_result = manager.verify_password("newpass")

    assert old_result.success is False
    assert old_result.reason == "INVALID_PASSWORD"

    assert new_result.success is True
    assert new_result.reason is None


def test_update_password_rejects_empty_value() -> None:
    manager = AuthManager(shared_password="nodepass")

    with pytest.raises(ValueError, match="new_password cannot be empty"):
        manager.update_password("   ")


def test_has_password_is_true_when_password_is_configured() -> None:
    manager = AuthManager(shared_password="nodepass")

    assert manager.has_password is True