"""Dependency-free reference checks for Interview Package Schema v1 fixtures.

This is test support, not production cryptography or a general JSON Schema/JCS
implementation.  The canonicalizer is exact for the v1 schema's JSON subset:
objects, arrays, strings, integers, booleans and null (no floating point values).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse


class PackageValidationError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _fail(code, detail=""):
    raise PackageValidationError(code, detail)


def _b64url_decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def canonicalize_v1(value):
    def reject_float(item):
        if isinstance(item, float):
            _fail("PACKAGE_SCHEMA_INVALID", "floating point values are outside the v1 signed subset")
        if isinstance(item, dict):
            for nested in item.values():
                reject_float(nested)
        elif isinstance(item, list):
            for nested in item:
                reject_float(nested)

    reject_float(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _resolve_ref(root, ref):
    if not ref.startswith("#/"):
        _fail("PACKAGE_SCHEMA_INVALID", f"unsupported schema reference {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def _is_type(value, expected):
    if expected == "object": return isinstance(value, dict)
    if expected == "array": return isinstance(value, list)
    if expected == "string": return isinstance(value, str)
    if expected == "integer": return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean": return isinstance(value, bool)
    if expected == "null": return value is None
    return False


def _check_format(value, name, path):
    try:
        if name == "uuid": uuid.UUID(value)
        elif name == "date-time":
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None: raise ValueError
        elif name == "uri":
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc: raise ValueError
    except (TypeError, ValueError) as exc:
        _fail("PACKAGE_SCHEMA_INVALID", f"{path} is not a valid {name}")


def _validate_schema_node(value, node, root, path="$"):
    if "$ref" in node:
        _validate_schema_node(value, _resolve_ref(root, node["$ref"]), root, path)
    for branch in node.get("allOf", []):
        _validate_schema_node(value, branch, root, path)
    if "type" in node and not _is_type(value, node["type"]):
        _fail("PACKAGE_SCHEMA_INVALID", f"{path} must be {node['type']}")
    if "const" in node and value != node["const"]:
        _fail("PACKAGE_SCHEMA_INVALID", f"{path} must equal {node['const']!r}")
    if "enum" in node and value not in node["enum"]:
        _fail("PACKAGE_SCHEMA_INVALID", f"{path} has an unsupported value")
    if isinstance(value, dict):
        required = set(node.get("required", []))
        missing = sorted(required - value.keys())
        if missing:
            _fail("PACKAGE_SCHEMA_INVALID", f"{path} is missing {missing[0]}")
        properties = node.get("properties", {})
        if node.get("additionalProperties") is False:
            extra = sorted(value.keys() - properties.keys())
            if extra:
                _fail("PACKAGE_SCHEMA_INVALID", f"{path} has unknown field {extra[0]}")
        for key, child in value.items():
            if key in properties:
                _validate_schema_node(child, properties[key], root, f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            _fail("PACKAGE_SCHEMA_INVALID", f"{path} has too few items")
        if len(value) > node.get("maxItems", len(value)):
            _fail("PACKAGE_SCOPE_TOO_LARGE", f"{path} has too many items")
        if node.get("uniqueItems"):
            serialized = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(serialized) != len(set(serialized)):
                _fail("PACKAGE_SCHEMA_INVALID", f"{path} contains duplicates")
        for index, child in enumerate(value):
            if "items" in node:
                _validate_schema_node(child, node["items"], root, f"{path}[{index}]")
    if isinstance(value, str):
        if len(value) < node.get("minLength", 0) or len(value) > node.get("maxLength", len(value)):
            _fail("PACKAGE_SCHEMA_INVALID", f"{path} has invalid length")
        if "pattern" in node and re.fullmatch(node["pattern"], value) is None:
            _fail("PACKAGE_SCHEMA_INVALID", f"{path} does not match its pattern")
        if "format" in node:
            _check_format(value, node["format"], path)
    if isinstance(value, int) and not isinstance(value, bool):
        if value < node.get("minimum", value) or value > node.get("maximum", value):
            _fail("PACKAGE_SCHEMA_INVALID", f"{path} is outside its numeric bounds")


def validate_against_schema(package, schema):
    _validate_schema_node(package, schema, schema)
    return True


# Minimal P-256/ES256 verification for the fixed synthetic vector only.
# Production code must use a maintained JOSE/cryptographic library.
_P256_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_P256_A = _P256_P - 3
_P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_P256_G = (
    0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
    0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5,
)


def _p256_add(left, right):
    if left is None: return right
    if right is None: return left
    x1, y1 = left; x2, y2 = right
    if x1 == x2 and (y1 + y2) % _P256_P == 0: return None
    if left == right:
        slope = ((3 * x1 * x1 + _P256_A) * pow(2 * y1, -1, _P256_P)) % _P256_P
    else:
        slope = ((y2 - y1) * pow(x2 - x1, -1, _P256_P)) % _P256_P
    x3 = (slope * slope - x1 - x2) % _P256_P
    return x3, (slope * (x1 - x3) - y1) % _P256_P


def _p256_multiply(point, scalar):
    result = None
    addend = point
    while scalar:
        if scalar & 1: result = _p256_add(result, addend)
        addend = _p256_add(addend, addend)
        scalar >>= 1
    return result


def _verify_es256(key, message, signature):
    try:
        if len(signature) != 64: return False
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        if not (1 <= r < _P256_N and 1 <= s < _P256_N): return False
        x_bytes = _b64url_decode(key["x"]); y_bytes = _b64url_decode(key["y"])
        if len(x_bytes) != 32 or len(y_bytes) != 32: return False
        x = int.from_bytes(x_bytes, "big"); y = int.from_bytes(y_bytes, "big")
        if not (0 <= x < _P256_P and 0 <= y < _P256_P): return False
        if (y * y - x * x * x - _P256_A * x - _P256_B) % _P256_P: return False
        digest = hashlib.sha256(message).digest()
        inverse = pow(s, -1, _P256_N)
        point = _p256_add(
            _p256_multiply(_P256_G, int.from_bytes(digest, "big") * inverse % _P256_N),
            _p256_multiply((x, y), r * inverse % _P256_N),
        )
        return point is not None and point[0] % _P256_N == r
    except (KeyError, ValueError, ZeroDivisionError, binascii.Error):
        return False


def verify_detached_jws(package, jwks):
    try:
        protected_segment, empty, signature_segment = package["proof"]["value"].split(".")
        if empty: _fail("PACKAGE_SIGNATURE_INVALID", "payload must be detached")
        header = json.loads(_b64url_decode(protected_segment))
    except (KeyError, TypeError, ValueError, binascii.Error):
        _fail("PACKAGE_SIGNATURE_INVALID", "malformed detached JWS")
    if not isinstance(header, dict):
        _fail("PACKAGE_SIGNATURE_INVALID", "protected header must be an object")
    expected = {
        "alg": "ES256",
        "cty": "application/vnd.careerground.interview-package+json",
        "typ": "careerground-interview-package+jws",
    }
    if any(header.get(key) != value for key, value in expected.items()) or set(header) != {"alg", "cty", "kid", "typ"}:
        _fail("PACKAGE_SIGNATURE_INVALID", "protected header is not the approved profile")
    matching_keys = [item for item in jwks.get("keys", []) if item.get("kid") == header.get("kid")]
    if len(matching_keys) != 1:
        _fail("PACKAGE_SIGNATURE_INVALID", "unknown or ambiguous signing key")
    key = matching_keys[0]
    if (key.get("kty"), key.get("crv"), key.get("alg"), key.get("use")) != ("EC", "P-256", "ES256", "sig") or "d" in key:
        _fail("PACKAGE_SIGNATURE_INVALID", "unknown or incompatible signing key")
    payload_segment = _b64url_encode(canonicalize_v1(package["payload"]))
    message = f"{protected_segment}.{payload_segment}".encode("ascii")
    try:
        valid = _verify_es256(key, message, _b64url_decode(signature_segment))
    except (KeyError, ValueError, binascii.Error):
        valid = False
    if not valid: _fail("PACKAGE_SIGNATURE_INVALID", "signature verification failed")
    return header


def _ids(items, key):
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        _fail("PACKAGE_REFERENCE_INVALID", f"duplicate {key}")
    return set(values)


def _require_subset(values, allowed, detail):
    missing = set(values) - set(allowed)
    if missing: _fail("PACKAGE_REFERENCE_INVALID", f"{detail}: {sorted(missing)[0]}")


def _embedded_content_hash(item):
    unsigned = {key: value for key, value in item.items() if key != "content_hash"}
    return _b64url_encode(hashlib.sha256(canonicalize_v1(unsigned)).digest())


def _validate_references(payload):
    claim_ids = _ids(payload["claims"], "claim_id")
    evidence_ids = _ids(payload["evidence"], "evidence_id")
    constraint_ids = _ids(payload["constraints"], "constraint_id")
    requirement_ids = _ids(payload["jd_requirements"], "requirement_id")
    unit_ids = _ids(payload["resume_units"], "unit_id")
    question_ids = _ids(payload["interview_plan"]["core_questions"], "question_id")
    del question_ids
    support_counts = {claim_id: 0 for claim_id in claim_ids}
    for link in payload["claim_evidence_links"]:
        _require_subset([link["claim_id"]], claim_ids, "link claim dangles")
        _require_subset([link["evidence_id"]], evidence_ids, "link evidence dangles")
        if link["relation_type"] == "SUPPORTS": support_counts[link["claim_id"]] += 1
    if any(count == 0 for count in support_counts.values()):
        _fail("PACKAGE_REFERENCE_INVALID", "each Claim needs SUPPORTS evidence")
    if any(count > 2 for count in support_counts.values()):
        _fail("PACKAGE_SCOPE_TOO_LARGE", "more than two Evidence excerpts support one Claim")
    for evidence in payload["evidence"]:
        _require_subset(evidence["claim_ids"], claim_ids, "Evidence claim dangles")
    for constraint in payload["constraints"]:
        allowed = claim_ids if constraint["target_type"] == "CLAIM" else evidence_ids if constraint["target_type"] == "EVIDENCE" else unit_ids if constraint["target_type"] == "RESUME_UNIT" else {payload["package_id"]}
        _require_subset(constraint["target_ids"], allowed, "constraint target dangles")
    for requirement in payload["jd_requirements"]:
        _require_subset(requirement["claim_ids"], claim_ids, "JD Claim dangles")
    for unit in payload["resume_units"]:
        _require_subset(unit["claim_ids"], claim_ids, "resume Claim dangles")
        _require_subset(unit["evidence_ids"], evidence_ids, "resume Evidence dangles")
        _require_subset(unit["constraint_ids"], constraint_ids, "resume constraint dangles")
    for question in payload["interview_plan"]["core_questions"]:
        _require_subset(question["claim_ids"], claim_ids, "question Claim dangles")
        _require_subset(question["jd_requirement_ids"], requirement_ids, "question JD requirement dangles")
        _require_subset(question["constraint_ids"], constraint_ids, "question constraint dangles")

    manifest = {(item["object_type"], item["object_id"]): item for item in payload["integrity_manifest"]}
    if len(manifest) != len(payload["integrity_manifest"]):
        _fail("PACKAGE_REFERENCE_INVALID", "duplicate manifest entry")
    refs = payload["provenance"]
    expected = [
        ("PROFILE", refs["profile"]["profile_id"], refs["profile"]),
        ("JD_ANALYSIS", refs["jd_analysis"]["artifact_id"], refs["jd_analysis"]),
        ("RESUME", refs["resume"]["artifact_id"], refs["resume"]),
        ("INTERVIEW_PLAN", refs["interview_plan"]["artifact_id"], refs["interview_plan"]),
    ]
    embedded = [
        *(('CLAIM', item['claim_id'], item) for item in payload['claims']),
        *(('EVIDENCE', item['evidence_id'], item) for item in payload['evidence']),
        *(('CONSTRAINT', item['constraint_id'], item) for item in payload['constraints']),
        *(('JD_REQUIREMENT', item['requirement_id'], item) for item in payload['jd_requirements']),
        *(('RESUME_UNIT', item['unit_id'], item) for item in payload['resume_units']),
    ]
    for object_type, object_id, source in expected + embedded:
        entry = manifest.get((object_type, object_id))
        if not entry or entry["content_hash"] != source["content_hash"]:
            _fail("PACKAGE_REFERENCE_INVALID", f"manifest mismatch for {object_type}:{object_id}")
        if "version" in source and entry.get("version") != source["version"]:
            _fail("PACKAGE_REFERENCE_INVALID", f"manifest version mismatch for {object_type}:{object_id}")
    for object_type, object_id, source in embedded:
        if source["content_hash"] != _embedded_content_hash(source):
            _fail("PACKAGE_REFERENCE_INVALID", f"content hash mismatch for {object_type}:{object_id}")


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_interview_package(
    package,
    schema,
    jwks,
    *,
    now="2026-09-23T00:00:00Z",
    authenticated_subject="acct-synthetic-001",
    registry_status="ISSUED",
    existing_session_id=None,
    supported_major=1,
    understood_capabilities=None,
    verify_signature=True,
):
    try:
        payload = package["payload"]
        package_major = int(payload["schema_version"].split(".", 1)[0])
    except (KeyError, TypeError, ValueError, AttributeError):
        _fail("PACKAGE_SCHEMA_INVALID", "missing or malformed schema_version")
    if package_major != supported_major:
        _fail("PACKAGE_SCHEMA_UNSUPPORTED")
    validate_against_schema(package, schema)
    understood = understood_capabilities or {
        "EVIDENCE_AWARE_QUESTIONS", "CONSTRAINT_GUARDS", "ONLINE_STATUS_CHECK", "SINGLE_SESSION_START"
    }
    if not set(payload["required_capabilities"]) <= set(understood):
        _fail("PACKAGE_SCHEMA_UNSUPPORTED", "required capability is not understood")
    if len(canonicalize_v1(payload)) > 512 * 1024:
        _fail("PACKAGE_SCOPE_TOO_LARGE", "canonical payload exceeds 512 KiB")
    if verify_signature:
        verify_detached_jws(package, jwks)
    issued = _parse_time(payload["issued_at"]); not_before = _parse_time(payload["not_before"]); expires = _parse_time(payload["expires_at"]); current = _parse_time(now)
    if not (issued <= not_before < expires) or expires - issued > timedelta(days=7):
        _fail("PACKAGE_SCHEMA_INVALID", "invalid package validity window")
    if current < not_before: _fail("PACKAGE_NOT_YET_VALID")
    if current >= expires: _fail("PACKAGE_EXPIRED")
    if payload["subject_id"] != authenticated_subject: _fail("PACKAGE_SUBJECT_MISMATCH")
    if registry_status == "REVOKED": _fail("PACKAGE_REVOKED")
    if registry_status != "ISSUED": _fail("PACKAGE_EXPIRED")
    if existing_session_id: _fail("PACKAGE_ALREADY_USED", existing_session_id)
    _validate_references(payload)
    return True
