from __future__ import annotations

import errno
import socket
from typing import Any, Callable

from core.models import NodeIdentity, Peer
from network.protocol import (
    MessageType,
    create_message,
    deserialize_message,
    message_has_type,
    serialize_message,
)
from utils.log_utils import get_logger


class SessionError(Exception):
    """
    Base exception for session-related failures.
    """


class SessionConnectionError(SessionError):
    """
    Raised when a TCP session connection fails.
    """


class SessionProtocolError(SessionError):
    """
    Raised when an invalid or unexpected protocol message is received.
    """


class SessionCancelledError(SessionError):
    """
    Raised when a local transfer cancellation interrupts an active socket send.
    """


class SessionClient:
    """
    TCP client responsible for initiating a NodeDrop session with a remote peer.

    Supported behaviors:
    - request_session():
        compatibility API for the existing tests
        opens a TCP connection, completes the session/auth handshake,
        returns the final response, then closes the socket.

    - open_authenticated_session():
        new API for transfer use
        opens a TCP connection, completes the session/auth handshake,
        and returns the authenticated persistent socket for transfer use.

    Transport framing for NodeDrop TCP messages:
    - every JSON protocol message is sent as:
        [4-byte big-endian length][UTF-8 JSON payload]
    - FILE_CHUNK raw bytes are sent immediately after the FILE_CHUNK message
      and must be read with the exact chunk_size declared in that message.
    """

    DEFAULT_CONNECT_TIMEOUT = 5.0
    DEFAULT_RECEIVE_TIMEOUT = 5.0
    DEFAULT_CLOSE_TIMEOUT = 1.0
    HEADER_SIZE_BYTES = 4
    INTERRUPTIBLE_SEND_TIMEOUT = 0.25
    INTERRUPTIBLE_SEND_BLOCK_SIZE = 64 * 1024

    def __init__(self, local_identity: NodeIdentity) -> None:
        self._logger = get_logger("network.session")
        self._local_identity = local_identity

    # ============================================================
    # Public API
    # ============================================================

    def request_session(
        self,
        peer: Peer,
        session_id: str,
        password: str,
    ) -> dict[str, Any]:
        """
        Open a TCP connection to a peer, request a session, and complete authentication.

        Compatibility API kept intentionally stable for the existing tests.

        Valid final outcomes returned:
        - SESSION_REJECTED
        - AUTH_SUCCESS
        - AUTH_FAILED
        """
        sock: socket.socket | None = None

        try:
            sock, final_response = self._open_authenticated_session_internal(
                peer=peer,
                session_id=session_id,
                password=password,
                raise_on_rejected_or_failed=False,
            )
            return final_response
        finally:
            if sock is not None:
                self.close_gracefully(sock, wait_for_remote_close=False)

    def open_authenticated_session(
        self,
        peer: Peer,
        session_id: str,
        password: str,
    ) -> tuple[socket.socket, dict[str, Any]]:
        """
        Open a persistent TCP connection to a peer and complete authentication.

        On success:
            returns (authenticated_socket, AUTH_SUCCESS_message)

        On valid non-success outcomes:
            - SESSION_REJECTED
            - AUTH_FAILED
          raises SessionProtocolError and closes the socket.

        Raises:
            SessionConnectionError
            SessionProtocolError
        """
        return self._open_authenticated_session_internal(
            peer=peer,
            session_id=session_id,
            password=password,
            raise_on_rejected_or_failed=True,
        )

    # ============================================================
    # Internal session/auth flow
    # ============================================================

    def _open_authenticated_session_internal(
        self,
        peer: Peer,
        session_id: str,
        password: str,
        raise_on_rejected_or_failed: bool,
    ) -> tuple[socket.socket, dict[str, Any]]:
        """
        Shared implementation for:
        - request_session()
        - open_authenticated_session()

        If raise_on_rejected_or_failed is:
        - False:
            returns final protocol messages SESSION_REJECTED / AUTH_FAILED
        - True:
            raises SessionProtocolError for SESSION_REJECTED / AUTH_FAILED
        """
        self._logger.info(
            "Opening TCP session to peer %s (%s) at %s:%s",
            peer.display_name,
            peer.peer_id,
            peer.ip_address,
            peer.tcp_port,
        )

        request_message = create_message(
            MessageType.SESSION_REQUEST,
            session_id=session_id,
            sender_id=self._local_identity.node_id,
            sender_name=self._local_identity.display_name,
        )

        sock: socket.socket | None = None

        try:
            sock = socket.create_connection(
                (peer.ip_address, peer.tcp_port),
                timeout=self.DEFAULT_CONNECT_TIMEOUT,
            )
            sock.settimeout(self.DEFAULT_RECEIVE_TIMEOUT)

            self.send_message(sock, request_message)

            self._logger.info(
                "SESSION_REQUEST sent to %s (%s), session_id=%s",
                peer.display_name,
                peer.peer_id,
                session_id,
            )

            session_response = self.receive_message(sock)

            if session_response.get("session_id") != session_id:
                self.close_gracefully(sock, wait_for_remote_close=False)
                raise SessionProtocolError(
                    "Session response contains an unexpected session_id."
                )

            if message_has_type(session_response, MessageType.SESSION_REJECTED):
                self._logger.info(
                    "Session rejected by peer %s (%s), session_id=%s, reason=%s",
                    peer.display_name,
                    peer.peer_id,
                    session_id,
                    session_response.get("reason"),
                )

                if raise_on_rejected_or_failed:
                    self.close_gracefully(sock, wait_for_remote_close=False)
                    raise SessionProtocolError(
                        f"Session rejected by peer: {session_response.get('reason', 'unknown reason')}"
                    )

                return sock, session_response

            if not message_has_type(session_response, MessageType.SESSION_ACCEPTED):
                self.close_gracefully(sock, wait_for_remote_close=False)
                raise SessionProtocolError(
                    f"Unexpected response type received: {session_response.get('type')!r}"
                )

            self._logger.info(
                "Session accepted by peer %s (%s), session_id=%s",
                peer.display_name,
                peer.peer_id,
                session_id,
            )

            auth_request = self.receive_message(sock)

            if auth_request.get("session_id") != session_id:
                self.close_gracefully(sock, wait_for_remote_close=False)
                raise SessionProtocolError(
                    "AUTH_REQUEST contains an unexpected session_id."
                )

            if not message_has_type(auth_request, MessageType.AUTH_REQUEST):
                self.close_gracefully(sock, wait_for_remote_close=False)
                raise SessionProtocolError(
                    f"Expected AUTH_REQUEST, received: {auth_request.get('type')!r}"
                )

            auth_response = create_message(
                MessageType.AUTH_RESPONSE,
                session_id=session_id,
                password=password,
            )
            self.send_message(sock, auth_response)

            self._logger.info(
                "AUTH_RESPONSE sent to %s (%s), session_id=%s",
                peer.display_name,
                peer.peer_id,
                session_id,
            )

            final_response = self.receive_message(sock)

            if final_response.get("session_id") != session_id:
                self.close_gracefully(sock, wait_for_remote_close=False)
                raise SessionProtocolError(
                    "Final auth response contains an unexpected session_id."
                )

            if message_has_type(final_response, MessageType.AUTH_SUCCESS):
                self._logger.info(
                    "Authentication succeeded with peer %s (%s), session_id=%s",
                    peer.display_name,
                    peer.peer_id,
                    session_id,
                )
                return sock, final_response

            if message_has_type(final_response, MessageType.AUTH_FAILED):
                self._logger.info(
                    "Authentication failed with peer %s (%s), session_id=%s, reason=%s",
                    peer.display_name,
                    peer.peer_id,
                    session_id,
                    final_response.get("reason"),
                )

                if raise_on_rejected_or_failed:
                    self.close_gracefully(sock, wait_for_remote_close=False)
                    raise SessionProtocolError(
                        f"Authentication failed: {final_response.get('reason', 'unknown reason')}"
                    )

                return sock, final_response

            self.close_gracefully(sock, wait_for_remote_close=False)
            raise SessionProtocolError(
                f"Unexpected final response type received: {final_response.get('type')!r}"
            )

        except socket.timeout as exc:
            if sock is not None:
                self.close_gracefully(sock, wait_for_remote_close=False)
            raise SessionConnectionError(
                f"Session/auth request timed out for peer {peer.display_name} "
                f"({peer.ip_address}:{peer.tcp_port})"
            ) from exc

        except OSError as exc:
            if sock is not None:
                self.close_gracefully(sock, wait_for_remote_close=False)
            raise SessionConnectionError(
                f"Failed to connect to peer {peer.display_name} "
                f"({peer.ip_address}:{peer.tcp_port}): {exc}"
            ) from exc

    # ============================================================
    # Transport primitives
    # ============================================================

    def send_message(
        self,
        sock: socket.socket,
        message: dict[str, Any],
        *,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> None:
        """
        Serialize and send one framed JSON protocol message.

        Wire format:
            [4-byte payload length][UTF-8 JSON bytes]
        """
        payload = serialize_message(message).encode("utf-8")
        payload_size = len(payload)

        if payload_size <= 0:
            raise SessionProtocolError("Cannot send an empty protocol payload.")

        header = payload_size.to_bytes(self.HEADER_SIZE_BYTES, byteorder="big")
        self._send_all_interruptible(
            sock,
            header,
            cancellation_check=cancellation_check,
        )
        self._send_all_interruptible(
            sock,
            payload,
            cancellation_check=cancellation_check,
        )

    def receive_message(self, sock: socket.socket) -> dict[str, Any]:
        """
        Receive one framed JSON protocol message.

        Wire format:
            [4-byte payload length][UTF-8 JSON bytes]
        """
        header = self.receive_exactly(sock, self.HEADER_SIZE_BYTES)
        payload_size = int.from_bytes(header, byteorder="big")

        if payload_size <= 0:
            raise SessionProtocolError("Received an invalid message length header.")

        payload = self.receive_exactly(sock, payload_size)

        try:
            return deserialize_message(payload)
        except Exception as exc:
            raise SessionProtocolError("Failed to deserialize protocol message.") from exc

    def send_bytes(
        self,
        sock: socket.socket,
        data: bytes | bytearray | memoryview,
        *,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> None:
        """
        Send raw bytes on the existing TCP stream.

        This is used immediately after a FILE_CHUNK JSON message.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like.")

        self._send_all_interruptible(
            sock,
            bytes(data),
            cancellation_check=cancellation_check,
        )

    def _send_all_interruptible(
        self,
        sock: socket.socket,
        data: bytes,
        *,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> None:
        if not data:
            return

        view = memoryview(data)
        bytes_sent = 0

        try:
            previous_timeout = sock.gettimeout()
        except OSError as exc:
            raise SessionConnectionError(f"Socket became unavailable before send: {exc}") from exc

        try:
            try:
                sock.settimeout(self.INTERRUPTIBLE_SEND_TIMEOUT)
            except OSError as exc:
                raise SessionConnectionError(f"Failed to configure socket send timeout: {exc}") from exc

            while bytes_sent < len(view):
                if cancellation_check is not None and cancellation_check():
                    raise SessionCancelledError("Transfer cancelled during socket send.")

                block_end = min(
                    bytes_sent + self.INTERRUPTIBLE_SEND_BLOCK_SIZE,
                    len(view),
                )
                chunk_view = view[bytes_sent:block_end]

                try:
                    sent_now = sock.send(chunk_view)
                except socket.timeout:
                    continue
                except OSError as exc:
                    if cancellation_check is not None and cancellation_check():
                        raise SessionCancelledError("Transfer cancelled during socket send.") from exc
                    raise SessionConnectionError(f"Socket send failed: {exc}") from exc

                if sent_now <= 0:
                    if cancellation_check is not None and cancellation_check():
                        raise SessionCancelledError("Transfer cancelled during socket send.")
                    raise SessionConnectionError("Socket send returned 0 bytes unexpectedly.")

                bytes_sent += sent_now
        finally:
            try:
                sock.settimeout(previous_timeout)
            except OSError:
                pass

    def receive_exactly(self, sock: socket.socket, size: int) -> bytes:
        """
        Read exactly `size` bytes from the socket.

        Raises SessionProtocolError if the remote peer closes the connection
        before enough bytes are received.
        """
        if size < 0:
            raise ValueError("size must be >= 0")

        if size == 0:
            return b""

        chunks: list[bytes] = []
        bytes_remaining = size

        while bytes_remaining > 0:
            chunk = sock.recv(bytes_remaining)

            if not chunk:
                raise SessionProtocolError(
                    "Remote peer closed connection before enough data was received."
                )

            chunks.append(chunk)
            bytes_remaining -= len(chunk)

        return b"".join(chunks)

    def close_gracefully(
        self,
        sock: socket.socket,
        *,
        wait_for_remote_close: bool = True,
        timeout: float | None = None,
    ) -> None:
        """
        Attempt a defensive TCP shutdown sequence.

        This method is intentionally tolerant:
        - the write side is shut down first so the peer can observe EOF
        - optional wait for remote close helps reduce abrupt resets on Windows
        - all shutdown/close errors are swallowed unless they signal a truly
          unexpected state elsewhere in the caller
        """
        effective_timeout = self.DEFAULT_CLOSE_TIMEOUT if timeout is None else timeout

        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError as exc:
            if not self._is_socket_already_closed_error(exc):
                self._logger.debug("Socket SHUT_WR ignored during graceful close: %s", exc)

        if wait_for_remote_close:
            self.wait_for_remote_close(sock, timeout=effective_timeout)

        try:
            sock.close()
        except OSError:
            pass

    def wait_for_remote_close(
        self,
        sock: socket.socket,
        timeout: float | None = None,
    ) -> bool:
        """
        Wait briefly for the remote peer to close its side of the connection.

        Returns True when EOF is observed. Returns False on timeout or when the
        socket is already unusable.
        """
        effective_timeout = self.DEFAULT_CLOSE_TIMEOUT if timeout is None else timeout

        try:
            previous_timeout = sock.gettimeout()
        except OSError:
            return False

        try:
            sock.settimeout(effective_timeout)
            while True:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    return False
                except OSError as exc:
                    if self.is_connection_reset_error(exc):
                        return True
                    if self._is_socket_already_closed_error(exc):
                        return True
                    return False

                if not chunk:
                    return True
        finally:
            try:
                sock.settimeout(previous_timeout)
            except OSError:
                pass

    @staticmethod
    def is_connection_reset_error(exc: BaseException) -> bool:
        if not isinstance(exc, OSError):
            return False

        if exc.errno in {errno.ECONNRESET, errno.EPIPE}:
            return True

        if getattr(exc, "winerror", None) == 10054:
            return True

        message = str(exc).lower()
        return "connection reset" in message or "forcibly closed" in message

    @staticmethod
    def _is_socket_already_closed_error(exc: OSError) -> bool:
        if exc.errno in {errno.ENOTCONN, errno.EBADF}:
            return True

        winerror = getattr(exc, "winerror", None)
        return winerror in {10038, 10057}