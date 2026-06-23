from __future__ import annotations

import json
import secrets
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OAuthProvider:
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str
    redirect_uri: str
    extra_token_params: dict[str, str] | None = None
    extra_headers: dict[str, str] | None = None


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorize_url(provider: OAuthProvider, state: str) -> str:
    params = {
        "client_id": provider.client_id,
        "redirect_uri": provider.redirect_uri,
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
    }
    return f"{provider.authorize_url}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(provider: OAuthProvider, code: str) -> dict[str, Any]:
    payload = {
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "code": code,
        "redirect_uri": provider.redirect_uri,
        "grant_type": "authorization_code",
    }
    if provider.extra_token_params:
        payload.update(provider.extra_token_params)

    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        provider.token_url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            **(provider.extra_headers or {}),
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            **(headers or {}),
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)

