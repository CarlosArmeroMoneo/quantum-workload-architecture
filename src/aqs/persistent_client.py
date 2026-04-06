from __future__ import annotations

import json
from pathlib import Path
import socket
from typing import Any

from .utils import canonical_json


PERSISTENT_EXECUTOR_PROTOCOL_VERSION = "aqs.persistent_executor.v1"


class PersistentClientError(RuntimeError):
    def __init__(self, message: str, *, raw_payload: Any | None = None):
        super().__init__(message)
        self.raw_payload = raw_payload


def _normalized_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve()).replace("\\", "/")


def _unix_socket_family() -> int:
    family = getattr(socket, "AF_UNIX", None)
    if family is None:
        raise RuntimeError("AF_UNIX sockets are unavailable on this platform")
    return int(family)


def _recv_json_line(reader: Any) -> dict[str, Any]:
    raw = reader.readline()
    if not raw:
        raise PersistentClientError("worker connection closed before a response was received")
    try:
        payload = json.loads(raw)
    except Exception as exc:  # pragma: no cover - exercised via client wrapper
        raise PersistentClientError(f"worker response was not valid JSON: {exc}", raw_payload=raw) from exc
    if not isinstance(payload, dict):
        raise PersistentClientError("worker response must decode to a JSON object", raw_payload=payload)
    return payload


def _send_json_line(writer: Any, payload: dict[str, Any]) -> None:
    writer.write(canonical_json(payload) + "\n")
    writer.flush()


class PersistentExecutorClient:
    def __init__(self, socket_path: str | Path, *, timeout_s: float = 60.0):
        self.socket_path = _normalized_path(socket_path)
        self.timeout_s = float(timeout_s)

    def close(self) -> None:
        return None

    def __enter__(self) -> PersistentExecutorClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _validate_response(self, payload: Any, *, command: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise PersistentClientError("worker response must be a JSON object", raw_payload=payload)
        protocol_version = payload.get("protocol_version")
        if protocol_version is not None and protocol_version != PERSISTENT_EXECUTOR_PROTOCOL_VERSION:
            raise PersistentClientError(
                (
                    "worker response protocol version mismatch: "
                    f"expected {PERSISTENT_EXECUTOR_PROTOCOL_VERSION!r}, got {protocol_version!r}"
                ),
                raw_payload=payload,
            )
        if payload.get("command") not in {None, command}:
            raise PersistentClientError(
                f"worker response command mismatch: expected {command!r}, got {payload.get('command')!r}",
                raw_payload=payload,
            )
        if "ok" not in payload:
            raise PersistentClientError("worker response must include an 'ok' field", raw_payload=payload)
        return payload

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        command = str(payload.get("command") or "")
        try:
            with socket.socket(_unix_socket_family(), socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout_s)
                sock.connect(self.socket_path)
                with sock.makefile("r", encoding="utf-8") as reader, sock.makefile("w", encoding="utf-8") as writer:
                    _send_json_line(writer, payload)
                    response = _recv_json_line(reader)
        except PersistentClientError:
            raise
        except Exception as exc:
            raise PersistentClientError(
                f"persistent executor request failed for command {command!r}: {exc}"
            ) from exc
        return self._validate_response(response, command=command)

    def _request_command(self, command: str, *, extra_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "command": command,
        }
        if extra_payload:
            payload.update(extra_payload)
        return self.request(payload)

    def ping(self) -> dict[str, Any]:
        return self._request_command("ping")

    def status(self) -> dict[str, Any]:
        return self._request_command("status")

    def execute_bundle(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._request_command("execute_bundle", extra_payload=request)

    def execute_plan_json(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._request_command("execute_plan_json", extra_payload=request)

    def shutdown(self) -> dict[str, Any]:
        return self._request_command("shutdown")


__all__ = [
    "PERSISTENT_EXECUTOR_PROTOCOL_VERSION",
    "PersistentClientError",
    "PersistentExecutorClient",
]
