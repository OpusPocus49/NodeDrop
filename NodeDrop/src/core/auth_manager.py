from __future__ import annotations

from dataclasses import dataclass

from utils.log_utils import get_logger


@dataclass(slots=True, frozen=True)
class AuthResult:
    """
    Result of a password verification attempt.
    """

    success: bool
    reason: str | None = None


class AuthManager:
    """
    Minimal authentication manager for NodeDrop V1.

    Responsibilities:
    - store the local shared password
    - validate a received password
    - expose a small, testable API to upper layers

    Non-responsibilities:
    - no network I/O
    - no GUI interaction
    - no encryption protocol
    - no persistent storage yet
    """

    def __init__(self, shared_password: str) -> None:
        self._logger = get_logger("core.auth_manager")
        self._shared_password = self._normalize_password(shared_password)

        if not self._shared_password:
            raise ValueError("shared_password cannot be empty.")

        self._logger.debug("AuthManager initialized.")

    @property
    def has_password(self) -> bool:
        """
        Return True if a local shared password is configured.
        """
        return bool(self._shared_password)

    def verify_password(self, provided_password: str) -> AuthResult:
        """
        Verify a password received from a remote peer.

        Returns:
            AuthResult describing whether authentication succeeded.
        """
        normalized = self._normalize_password(provided_password)

        if not normalized:
            self._logger.warning("Authentication failed: empty password received.")
            return AuthResult(
                success=False,
                reason="EMPTY_PASSWORD",
            )

        if normalized != self._shared_password:
            self._logger.warning("Authentication failed: invalid password.")
            return AuthResult(
                success=False,
                reason="INVALID_PASSWORD",
            )

        self._logger.info("Authentication succeeded.")
        return AuthResult(
            success=True,
            reason=None,
        )

    def update_password(self, new_password: str) -> None:
        """
        Replace the current shared password.

        Raises:
            ValueError if the new password is empty after normalization.
        """
        normalized = self._normalize_password(new_password)

        if not normalized:
            raise ValueError("new_password cannot be empty.")

        self._shared_password = normalized
        self._logger.info("Shared password updated.")

    @staticmethod
    def _normalize_password(value: str) -> str:
        """
        Normalize an input password for V1 validation rules.

        Current V1 rule:
        - trim surrounding whitespace

        Notes:
        - internal whitespace is preserved
        - comparison remains case-sensitive
        """
        if not isinstance(value, str):
            raise TypeError("Password value must be a string.")

        return value.strip()