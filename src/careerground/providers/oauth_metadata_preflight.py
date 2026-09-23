"""Static MCP OAuth metadata preflight; this does not authenticate a user or token."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, ValidationError


class RegistrationMode(StrEnum):
    CIMD = "CIMD"
    PREREGISTERED = "PREREGISTERED"
    DCR = "DCR"


class AuthorizationServerMetadata(BaseModel):
    """Only fields needed for the first ChatGPT/MCP discovery gate."""

    model_config = ConfigDict(extra="allow")  # OAuth metadata is extensible.

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    code_challenge_methods_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]
    client_id_metadata_document_supported: bool = False
    registration_endpoint: str | None = None
    authorization_response_iss_parameter_supported: bool = False


@dataclass(frozen=True)
class MetadataPreflight:
    issuer: str
    registration_mode: RegistrationMode
    compatible_token_auth_methods: tuple[str, ...]
    declares_authorization_response_iss: bool


class MetadataRejected(ValueError):
    """The advertised metadata cannot pass the selected MCP registration gate."""


def _require_https_url(value: str, *, field: str, allow_query: bool = False) -> None:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        _ = parsed.port  # Validate port syntax even though the port is not otherwise needed.
    except ValueError as exc:
        raise MetadataRejected(f"{field} is not a valid HTTPS URL") from exc
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise MetadataRejected(f"{field} must be an HTTPS URL without userinfo")
    if parsed.fragment or (parsed.query and not allow_query):
        raise MetadataRejected(f"{field} has an unsupported query or fragment")


def assess_mcp_oauth_metadata(
    raw_metadata: Mapping[str, object],
    *,
    expected_issuer: str,
    registration_mode: RegistrationMode,
) -> MetadataPreflight:
    """Check declared capabilities only; runtime resource/audience behavior remains unproven."""

    try:
        metadata = AuthorizationServerMetadata.model_validate(raw_metadata)
    except ValidationError as exc:
        raise MetadataRejected("OAuth discovery metadata is missing or malformed") from exc

    _require_https_url(metadata.issuer, field="issuer")
    for field in ("authorization_endpoint", "token_endpoint"):
        _require_https_url(getattr(metadata, field), field=field, allow_query=True)
    if metadata.issuer != expected_issuer:
        raise MetadataRejected("OAuth issuer does not exactly match the selected issuer")
    if "S256" not in metadata.code_challenge_methods_supported:
        raise MetadataRejected("OAuth metadata does not advertise PKCE S256")

    if registration_mode is RegistrationMode.CIMD:
        if not metadata.client_id_metadata_document_supported:
            raise MetadataRejected("OAuth metadata does not advertise CIMD")
        allowed = ("none", "private_key_jwt")
    elif registration_mode is RegistrationMode.DCR:
        if metadata.registration_endpoint is None:
            raise MetadataRejected("OAuth metadata does not advertise DCR")
        _require_https_url(
            metadata.registration_endpoint, field="registration_endpoint", allow_query=True
        )
        allowed = ("none", "client_secret_post", "client_secret_basic")
    else:
        allowed = ("none", "client_secret_post", "client_secret_basic", "private_key_jwt")

    methods = tuple(
        method for method in allowed if method in metadata.token_endpoint_auth_methods_supported
    )
    if not methods:
        raise MetadataRejected("OAuth token endpoint has no compatible authentication method")
    return MetadataPreflight(
        issuer=metadata.issuer,
        registration_mode=registration_mode,
        compatible_token_auth_methods=methods,
        declares_authorization_response_iss=metadata.authorization_response_iss_parameter_supported,
    )
