from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class ToxiproxyError(RuntimeError):
    pass


class ToxiproxyClient:
    """Minimal stdlib Toxiproxy client restricted to local test daemons."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8474",
        *,
        opener: Callable[..., Any] = urlopen,
        timeout: float = 2.0,
    ):
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Toxiproxy control plane must be loopback HTTP only")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Toxiproxy base URL must not contain credentials, query, or fragment")
        self.base_url = base_url.rstrip("/")
        self._opener = opener
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "User-Agent": "astra-agent-os-ci"},
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            raise ToxiproxyError(f"Toxiproxy API returned HTTP {exc.code}") from exc

    def version(self) -> str:
        payload = self._request("GET", "/version")
        if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
            raise ToxiproxyError("invalid Toxiproxy version response")
        return payload["version"]

    def reset(self) -> None:
        self._request("POST", "/reset")

    def delete_proxy(self, name: str) -> None:
        self._request("DELETE", f"/proxies/{quote(name, safe='')}", allow_not_found=True)

    def create_proxy(self, name: str, listen: str, upstream: str) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/proxies",
            {"name": name, "listen": listen, "upstream": upstream, "enabled": True},
        )
        if not isinstance(payload, dict):
            raise ToxiproxyError("invalid proxy creation response")
        return payload

    def add_toxic(
        self,
        proxy: str,
        *,
        name: str,
        toxic_type: str,
        stream: str = "downstream",
        toxicity: float = 1.0,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if stream not in {"upstream", "downstream"}:
            raise ValueError("stream must be upstream or downstream")
        payload = self._request(
            "POST",
            f"/proxies/{quote(proxy, safe='')}/toxics",
            {
                "name": name,
                "type": toxic_type,
                "stream": stream,
                "toxicity": toxicity,
                "attributes": attributes or {},
            },
        )
        if not isinstance(payload, dict):
            raise ToxiproxyError("invalid toxic creation response")
        return payload

    def remove_toxic(self, proxy: str, name: str) -> None:
        self._request(
            "DELETE",
            f"/proxies/{quote(proxy, safe='')}/toxics/{quote(name, safe='')}",
            allow_not_found=True,
        )
