from __future__ import annotations

import errno
import socket
import threading
from typing import Any, Callable

from network.protocol import (
    MessageSerializationError,
    MessageType,
    create_message,
    deserialize_message,
    message_has_type,
    serialize_message,
)
from utils.config import (
    MAX_PENDING_CONNECTIONS,
    TCP_READ_TIMEOUT_SECONDS,
    TRANSFER_TCP_PORT,
)
from utils.log_utils import get_logger

SessionRequestHandler = Callable[[dict[str, Any], tuple[str, int]], dict[str, Any] | None]
AuthResponseHandler = Callable[[dict[str, Any], tuple[str, int]], dict[str, Any] | None]
TransferMessageHandler = Callable[
    [dict[str, Any], bytes | None, dict[str, Any], tuple[str, int]],
    None,
]


class ListenerError(Exception):
    """
    Base exception for listener-related failures.
    """


class ListenerProtocolError(ListenerError):
    """
    Raised when a TCP framing or protocol error occurs.
    """


class ClientDisconnectedError(ListenerError):
    """
    Raised when a client disconnects cleanly while the listener is waiting
    for the next framed message.
    """


class SessionListener:
    """
    TCP listener responsible for handling incoming NodeDrop session requests.

    V1 scope:
    - listen on the NodeDrop TCP port
    - accept incoming TCP connections
    - process SESSION_REQUEST
    - if accepted, perform authentication handshake
    - if authentication succeeds, keep the connection open
    - receive transfer-related messages on the same authenticated session

    Transport framing:
    - every JSON protocol message is sent as:
        [4-byte big-endian length][UTF-8 JSON payload]
    - FILE_CHUNK raw bytes must be sent immediately after the FILE_CHUNK message
      and must be read with the exact chunk_size declared in that message
    """

    SERVER_SOCKET_TIMEOUT_SECONDS = 1.0
    HEADER_SIZE_BYTES = 4

    def __init__(
        self,
        on_session_requested: SessionRequestHandler | None = None,
        on_auth_response: AuthResponseHandler | None = None,
        on_transfer_message: TransferMessageHandler | None = None,
    ) -> None:
        self._logger = get_logger("network.listener")

        self._tcp_port = TRANSFER_TCP_PORT
        self._socket_timeout = self.SERVER_SOCKET_TIMEOUT_SECONDS
        self._client_timeout = TCP_READ_TIMEOUT_SECONDS
        self._backlog = MAX_PENDING_CONNECTIONS

        self._on_session_requested = on_session_requested
        self._on_auth_response = on_auth_response
        self._on_transfer_message = on_transfer_message

        self._stop_event = threading.Event()
        self._server_thread: threading.Thread | None = None
        self._server_socket: socket.socket | None = None

        self._running = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        """
        Start the TCP session listener in a background thread.
        """
        with self._lock:
            if self._running:
                self._logger.warning("SessionListener is already running.")
                return

            self._logger.info(
                "Starting SessionListener on TCP port %s.",
                self._tcp_port,
            )

            self._stop_event.clear()

            server_thread = threading.Thread(
                target=self._server_loop,
                name="NodeDropSessionListener",
                daemon=True,
            )
            self._server_thread = server_thread
            self._running = True

        try:
            server_thread.start()
        except Exception:
            with self._lock:
                self._server_thread = None
                self._running = False
                self._stop_event.set()
            raise

    def stop(self) -> None:
        """
        Stop the TCP session listener cleanly.
        """
        with self._lock:
            if not self._running:
                self._logger.warning("SessionListener is not running.")
                return

            self._logger.info("Stopping SessionListener.")
            self._stop_event.set()

            server_socket = self._server_socket
            server_thread = self._server_thread

            self._server_socket = None
            self._server_thread = None
            self._running = False

        if server_socket is not None:
            try:
                server_socket.close()
            except OSError:
                pass

        if server_thread is not None:
            server_thread.join(timeout=2.0)

        self._logger.info("SessionListener stopped.")

    def _server_loop(self) -> None:
        """
        Main server loop accepting incoming TCP connections.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                self._server_socket = server_socket
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(("0.0.0.0", self._tcp_port))
                server_socket.listen(self._backlog)
                server_socket.settimeout(self._socket_timeout)

                self._logger.info(
                    "Session listener bound on 0.0.0.0:%s.",
                    self._tcp_port,
                )

                while not self._stop_event.is_set():
                    try:
                        client_socket, client_address = server_socket.accept()
                        client_socket.settimeout(self._client_timeout)

                        self._logger.info(
                            "Incoming TCP connection from %s:%s.",
                            client_address[0],
                            client_address[1],
                        )

                        client_thread = threading.Thread(
                            target=self._handle_client,
                            args=(client_socket, client_address),
                            name=f"NodeDropSessionClient-{client_address[0]}:{client_address[1]}",
                            daemon=True,
                        )
                        client_thread.start()

                    except socket.timeout:
                        continue

                    except OSError as exc:
                        if self._stop_event.is_set():
                            break
                        self._logger.warning("Listener socket error: %s", exc)

                    except Exception as exc:
                        self._logger.exception("Unexpected error in server loop: %s", exc)

        except Exception as exc:
            self._logger.exception("Failed to initialize SessionListener: %s", exc)

        finally:
            self._server_socket = None

    def _handle_client(self, client_socket: socket.socket, client_address: tuple[str, int]) -> None:
        """
        Handle a single incoming client connection.
        """
        session_context: dict[str, Any] | None = None

        try:
            with client_socket:
                message = self._receive_message(
                    client_socket,
                    client_address,
                    allow_immediate_eof=False,
                )

                if not message_has_type(message, MessageType.SESSION_REQUEST):
                    self._logger.warning(
                        "Unexpected message type received from %s:%s: %s",
                        client_address[0],
                        client_address[1],
                        message.get("type"),
                    )
                    rejection = create_message(
                        MessageType.SESSION_REJECTED,
                        session_id=message.get("session_id", "unknown"),
                        reason="Unexpected message type for session listener.",
                    )
                    self._send_message(client_socket, rejection)
                    return

                session_response = self._handle_session_request(message, client_address)
                self._send_message(client_socket, session_response)

                if not message_has_type(session_response, MessageType.SESSION_ACCEPTED):
                    return

                session_id = message["session_id"]
                sender_id = message.get("sender_id")
                sender_name = message.get("sender_name")

                auth_request = create_message(
                    MessageType.AUTH_REQUEST,
                    session_id=session_id,
                )
                self._send_message(client_socket, auth_request)

                auth_response = self._receive_message(
                    client_socket,
                    client_address,
                    allow_immediate_eof=False,
                )

                if not message_has_type(auth_response, MessageType.AUTH_RESPONSE):
                    failure = create_message(
                        MessageType.AUTH_FAILED,
                        session_id=session_id,
                        reason="Expected AUTH_RESPONSE.",
                    )
                    self._send_message(client_socket, failure)
                    return

                if auth_response.get("session_id") != session_id:
                    failure = create_message(
                        MessageType.AUTH_FAILED,
                        session_id=session_id,
                        reason="Session ID mismatch during authentication.",
                    )
                    self._send_message(client_socket, failure)
                    return

                final_response = self._handle_auth_response(auth_response, client_address)
                self._send_message(client_socket, final_response)

                if not message_has_type(final_response, MessageType.AUTH_SUCCESS):
                    return

                session_context = {
                    "session_id": session_id,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "client_ip": client_address[0],
                    "client_port": client_address[1],
                    "client_socket": client_socket,
                    "transfer_complete_received": False,
                    "transfer_ack_sent": False,
                    "session_close_received": False,
                    "remote_disconnect_after_ack": False,
                }

                self._logger.info(
                    "Authenticated session established with %s (%s) at %s:%s, session_id=%s",
                    sender_name,
                    sender_id,
                    client_address[0],
                    client_address[1],
                    session_id,
                )

                self._handle_authenticated_stream(
                    client_socket=client_socket,
                    client_address=client_address,
                    session_context=session_context,
                )

        except MessageSerializationError as exc:
            self._logger.warning(
                "Invalid protocol payload received from %s:%s: %s",
                client_address[0],
                client_address[1],
                exc,
            )

        except ClientDisconnectedError:
            if self._is_expected_disconnect(session_context):
                if session_context is not None:
                    session_context["remote_disconnect_after_ack"] = True
                self._logger.info(
                    "Client %s:%s closed the authenticated session after transfer finalization.",
                    client_address[0],
                    client_address[1],
                )
            else:
                self._logger.info(
                    "Client %s:%s closed the authenticated session.",
                    client_address[0],
                    client_address[1],
                )

        except ListenerProtocolError as exc:
            self._logger.warning(
                "Protocol error while handling client %s:%s: %s",
                client_address[0],
                client_address[1],
                exc,
            )

        except socket.timeout:
            self._logger.warning(
                "Client %s:%s timed out while waiting for data.",
                client_address[0],
                client_address[1],
            )

        except OSError as exc:
            if self._is_expected_disconnect(session_context) and self._is_connection_reset_error(exc):
                if session_context is not None:
                    session_context["remote_disconnect_after_ack"] = True
                self._logger.info(
                    "Connection reset by %s:%s after transfer finalization (treated as normal close).",
                    client_address[0],
                    client_address[1],
                )
            else:
                self._logger.warning(
                    "Socket error while handling client %s:%s: %s",
                    client_address[0],
                    client_address[1],
                    exc,
                )

        except Exception as exc:
            self._logger.exception(
                "Unexpected error while handling client %s:%s: %s",
                client_address[0],
                client_address[1],
                exc,
            )

    def _handle_authenticated_stream(
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
        session_context: dict[str, Any],
    ) -> None:
        """
        Handle the post-authenticated message stream for a single session.

        V1 constraints:
        - one transfer per session
        - one job per session
        - no multiplexing

        Important:
        The connection must remain open long enough for the receiver side
        to send TRANSFER_ACK back to the sender after TRANSFER_COMPLETE.
        """
        while not self._stop_event.is_set():
            message = self._receive_message(
                client_socket,
                client_address,
                allow_immediate_eof=True,
            )

            message_type = message.get("type")

            if message.get("session_id") not in (None, session_context["session_id"]):
                raise ListenerProtocolError(
                    "Received a post-auth message with an unexpected session_id."
                )

            chunk_data: bytes | None = None

            if message_has_type(message, MessageType.FILE_CHUNK):
                chunk_size = message.get("chunk_size")

                if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
                    raise ListenerProtocolError(
                        "FILE_CHUNK message contains an invalid chunk_size."
                    )

                if chunk_size < 0:
                    raise ListenerProtocolError(
                        "FILE_CHUNK message contains a negative chunk_size."
                    )

                chunk_data = self._receive_exactly(
                    client_socket,
                    chunk_size,
                    allow_immediate_eof=False,
                )

            self._logger.debug(
                "Post-auth message received from %s:%s: %s",
                client_address[0],
                client_address[1],
                message_type,
            )

            self._dispatch_transfer_message(
                message=message,
                chunk_data=chunk_data,
                session_context=session_context,
                client_address=client_address,
            )

            if message_has_type(message, MessageType.TRANSFER_ERROR):
                self._logger.info(
                    "TRANSFER_ERROR received for session_id=%s from %s:%s",
                    session_context["session_id"],
                    client_address[0],
                    client_address[1],
                )
                return

            if message_has_type(message, MessageType.SESSION_CLOSE):
                session_context["session_close_received"] = True
                self._logger.info(
                    "SESSION_CLOSE received for session_id=%s from %s:%s",
                    session_context["session_id"],
                    client_address[0],
                    client_address[1],
                )
                return

            if message_has_type(message, MessageType.TRANSFER_COMPLETE):
                session_context["transfer_complete_received"] = True
                session_context["transfer_ack_sent"] = True
                self._logger.info(
                    "TRANSFER_COMPLETE received for session_id=%s from %s:%s",
                    session_context["session_id"],
                    client_address[0],
                    client_address[1],
                )
                continue

    def _dispatch_transfer_message(
        self,
        message: dict[str, Any],
        chunk_data: bytes | None,
        session_context: dict[str, Any],
        client_address: tuple[str, int],
    ) -> None:
        """
        Dispatch one authenticated post-auth message to the configured transfer callback.

        The listener remains transport-oriented:
        - it receives framed JSON
        - it reads raw FILE_CHUNK bytes
        - it delegates business handling upward
        """
        if self._on_transfer_message is None:
            raise ListenerProtocolError(
                "Received transfer data but no transfer handler is configured."
            )

        self._on_transfer_message(
            message,
            chunk_data,
            session_context,
            client_address,
        )

    def _handle_session_request(
        self,
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any]:
        """
        Process a SESSION_REQUEST and return a response message.
        """
        session_id = message["session_id"]
        sender_id = message.get("sender_id")
        sender_name = message.get("sender_name")

        self._logger.info(
            "SESSION_REQUEST received from %s (%s) at %s:%s, session_id=%s",
            sender_name,
            sender_id,
            client_address[0],
            client_address[1],
            session_id,
        )

        if self._on_session_requested is not None:
            try:
                custom_response = self._on_session_requested(message, client_address)
                if custom_response is not None:
                    return custom_response

            except Exception as exc:
                self._logger.exception("Session request callback failed: %s", exc)
                return create_message(
                    MessageType.SESSION_REJECTED,
                    session_id=session_id,
                    reason="Internal listener callback error.",
                )

        return create_message(
            MessageType.SESSION_ACCEPTED,
            session_id=session_id,
        )

    def _handle_auth_response(
        self,
        message: dict[str, Any],
        client_address: tuple[str, int],
    ) -> dict[str, Any]:
        """
        Process an AUTH_RESPONSE and return AUTH_SUCCESS or AUTH_FAILED.
        """
        session_id = message["session_id"]

        self._logger.info(
            "AUTH_RESPONSE received from %s:%s for session_id=%s",
            client_address[0],
            client_address[1],
            session_id,
        )

        if self._on_auth_response is not None:
            try:
                custom_response = self._on_auth_response(message, client_address)
                if custom_response is not None:
                    return custom_response

            except Exception as exc:
                self._logger.exception("Auth response callback failed: %s", exc)
                return create_message(
                    MessageType.AUTH_FAILED,
                    session_id=session_id,
                    reason="Internal authentication callback error.",
                )

        return create_message(
            MessageType.AUTH_FAILED,
            session_id=session_id,
            reason="Authentication handler is not configured.",
        )

    def _send_message(self, client_socket: socket.socket, message: dict[str, Any]) -> None:
        """
        Serialize and send one framed protocol message.

        Wire format:
            [4-byte payload length][UTF-8 JSON bytes]
        """
        payload = serialize_message(message).encode("utf-8")
        payload_size = len(payload)

        if payload_size <= 0:
            raise ListenerProtocolError("Cannot send an empty protocol payload.")

        header = payload_size.to_bytes(self.HEADER_SIZE_BYTES, byteorder="big")
        client_socket.sendall(header)
        client_socket.sendall(payload)

    def _receive_message(
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
        allow_immediate_eof: bool,
    ) -> dict[str, Any]:
        """
        Receive and deserialize one framed protocol message.

        Wire format:
            [4-byte payload length][UTF-8 JSON bytes]
        """
        header = self._receive_exactly(
            client_socket,
            self.HEADER_SIZE_BYTES,
            allow_immediate_eof=allow_immediate_eof,
        )
        payload_size = int.from_bytes(header, byteorder="big")

        if payload_size <= 0:
            raise ListenerProtocolError("Received an invalid message length header.")

        payload = self._receive_exactly(
            client_socket,
            payload_size,
            allow_immediate_eof=False,
        )

        try:
            return deserialize_message(payload)
        except MessageSerializationError:
            raise
        except Exception as exc:
            raise ListenerProtocolError("Failed to deserialize protocol message.") from exc

    def _receive_exactly(
        self,
        client_socket: socket.socket,
        size: int,
        allow_immediate_eof: bool,
    ) -> bytes:
        """
        Read exactly `size` bytes from the client socket.

        If allow_immediate_eof is True and the peer closes the connection before any
        byte is received, ClientDisconnectedError is raised instead of a protocol error.
        """
        if size < 0:
            raise ValueError("size must be >= 0")

        if size == 0:
            return b""

        chunks: list[bytes] = []
        bytes_remaining = size
        bytes_received = 0

        while bytes_remaining > 0:
            chunk = client_socket.recv(bytes_remaining)

            if not chunk:
                if allow_immediate_eof and bytes_received == 0:
                    raise ClientDisconnectedError("Client closed the connection cleanly.")

                raise ListenerProtocolError(
                    "Remote client closed connection before enough data was received."
                )

            chunks.append(chunk)
            bytes_received += len(chunk)
            bytes_remaining -= len(chunk)

        return b"".join(chunks)

    @staticmethod
    def _is_connection_reset_error(exc: BaseException) -> bool:
        if not isinstance(exc, OSError):
            return False

        if exc.errno in {errno.ECONNRESET, errno.EPIPE}:
            return True

        if getattr(exc, "winerror", None) == 10054:
            return True

        message = str(exc).lower()
        return "connection reset" in message or "forcibly closed" in message

    @staticmethod
    def _is_expected_disconnect(session_context: dict[str, Any] | None) -> bool:
        if session_context is None:
            return False

        if session_context.get("session_close_received"):
            return True

        return bool(
            session_context.get("transfer_complete_received")
            and session_context.get("transfer_ack_sent")
        )