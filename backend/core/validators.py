"""
OryxShield — Validators
=================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

All validators raise django.core.exceptions.ValidationError on failure.
DRF serializer fields accept Django validators directly.

Sections
--------
String validators
Numeric validators
Date / time validators
Geographic validators
Phone / email validators
Security validators (passwords, API keys, tokens)
File validators
Surveillance / domain validators
"""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# String validators
# ---------------------------------------------------------------------------

def validate_not_blank(value: str) -> None:
    if not value or not value.strip():
        raise ValidationError(_("This field may not be blank."))


def validate_min_length(value: str, min_length: int, field_name: str = "Value") -> None:
    if len(value) < min_length:
        raise ValidationError(
            _("%(field)s must be at least %(min)d characters."),
            params={"field": field_name, "min": min_length},
        )


def validate_max_length(value: str, max_length: int, field_name: str = "Value") -> None:
    if len(value) > max_length:
        raise ValidationError(
            _("%(field)s must not exceed %(max)d characters."),
            params={"field": field_name, "max": max_length},
        )


def validate_alphanumeric(value: str) -> None:
    if not value.isalnum():
        raise ValidationError(_("Only letters and digits are allowed."))


def validate_uppercase_key(value: str) -> None:
    if not value.isupper():
        raise ValidationError(_("Key must be in UPPER_CASE format (e.g. MAX_RETRIES)."))


def validate_slug(value: str) -> None:
    if not re.match(r"^[-\w]+$", value):
        raise ValidationError(_("Enter a valid slug (letters, digits, hyphens, underscores only)."))


def validate_no_html(value: str) -> None:
    if re.search(r"<[^>]+>", value):
        raise ValidationError(_("HTML tags are not permitted."))


def validate_no_sql_injection(value: str) -> None:
    patterns = [
        r"(\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bUNION\b)",
        r"(--|;|\/\*|\*\/)",
    ]
    for pattern in patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValidationError(_("Potentially unsafe SQL content detected."))


def validate_json_string(value: str) -> None:
    try:
        json.loads(value)
    except (json.JSONDecodeError, TypeError):
        raise ValidationError(_("Enter a valid JSON string."))


# ---------------------------------------------------------------------------
# Numeric validators
# ---------------------------------------------------------------------------

def validate_positive(value) -> None:
    try:
        if Decimal(str(value)) <= 0:
            raise ValidationError(_("Value must be positive (greater than zero)."))
    except InvalidOperation:
        raise ValidationError(_("Enter a valid number."))


def validate_non_negative(value) -> None:
    try:
        if Decimal(str(value)) < 0:
            raise ValidationError(_("Value must be zero or positive."))
    except InvalidOperation:
        raise ValidationError(_("Enter a valid number."))


def validate_percentage(value) -> None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Enter a valid number."))
    if not (0 <= f <= 100):
        raise ValidationError(_("Percentage must be between 0 and 100."))


def validate_integer_range(value: int, min_val: int, max_val: int) -> None:
    if not (min_val <= value <= max_val):
        raise ValidationError(
            _("Value must be between %(min)d and %(max)d."),
            params={"min": min_val, "max": max_val},
        )


def validate_latitude(value) -> None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Enter a valid number."))
    if not (-90 <= f <= 90):
        raise ValidationError(_("Latitude must be between -90 and 90."))


def validate_longitude(value) -> None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Enter a valid number."))
    if not (-180 <= f <= 180):
        raise ValidationError(_("Longitude must be between -180 and 180."))


def validate_population(value: int) -> None:
    if value < 0:
        raise ValidationError(_("Population cannot be negative."))
    if value > 10_000_000_000:
        raise ValidationError(_("Population value is unrealistically large."))


# ---------------------------------------------------------------------------
# Date / time validators
# ---------------------------------------------------------------------------

def validate_past_date(value: date | datetime) -> None:
    check = value.date() if isinstance(value, datetime) else value
    if check >= date.today():
        raise ValidationError(_("Date must be in the past."))


def validate_future_date(value: date | datetime) -> None:
    check = value.date() if isinstance(value, datetime) else value
    if check <= date.today():
        raise ValidationError(_("Date must be in the future."))


def validate_future_datetime(value: datetime) -> None:
    if value <= timezone.now():
        raise ValidationError(_("Datetime must be in the future."))


def validate_date_not_too_old(value: date, max_years: int = 150) -> None:
    from dateutil.relativedelta import relativedelta  # type: ignore
    if value < date.today() - relativedelta(years=max_years):
        raise ValidationError(_("Date is too far in the past."))


def validate_date_range(start: date, end: date) -> None:
    if start >= end:
        raise ValidationError(_("Start date must be before end date."))


def validate_reasonable_birth_date(value: date) -> None:
    today = date.today()
    age = (today - value).days / 365.25
    if age < 0:
        raise ValidationError(_("Birth date cannot be in the future."))
    if age > 130:
        raise ValidationError(_("Birth date is unrealistically old."))


# ---------------------------------------------------------------------------
# Geographic validators
# ---------------------------------------------------------------------------

def validate_coordinates(lat, lng) -> None:
    validate_latitude(lat)
    validate_longitude(lng)


def validate_geojson(value: dict) -> None:
    if not isinstance(value, dict):
        raise ValidationError(_("GeoJSON must be a JSON object."))
    if value.get("type") not in {
        "Point", "MultiPoint", "LineString", "MultiLineString",
        "Polygon", "MultiPolygon", "GeometryCollection", "Feature", "FeatureCollection",
    }:
        raise ValidationError(_("Invalid GeoJSON type."))
    if "coordinates" not in value and value.get("type") != "FeatureCollection":
        raise ValidationError(_("GeoJSON object must contain coordinates."))


def validate_location_code(value: str) -> None:
    if not re.match(r"^[A-Z0-9_-]{2,50}$", value):
        raise ValidationError(
            _("Location code must be 2-50 uppercase letters, digits, hyphens or underscores.")
        )


# ---------------------------------------------------------------------------
# Phone / email validators
# ---------------------------------------------------------------------------

def validate_phone_number(value: str) -> None:
    cleaned = re.sub(r"\D", "", value)
    if not (7 <= len(cleaned) <= 15):
        raise ValidationError(_("Enter a valid phone number (7-15 digits)."))


def validate_namibian_phone(value: str) -> None:
    cleaned = re.sub(r"\D", "", value)
    # Accept: 07xxxxxxxx, 01xxxxxxxx, 2547xxxxxxxx, +2647xxxxxxxx
    if not re.match(r"^(254|0)[17]\d{8}$", cleaned):
        raise ValidationError(_("Enter a valid Namibian phone number."))


def validate_email(value: str) -> None:
    try:
        django_validate_email(value)
    except ValidationError:
        raise ValidationError(_("Enter a valid email address."))


def validate_email_domain(value: str, allowed_domains: list[str]) -> None:
    domain = value.split("@")[-1].lower() if "@" in value else ""
    if domain not in [d.lower() for d in allowed_domains]:
        raise ValidationError(
            _("Email domain is not allowed. Permitted: %(domains)s"),
            params={"domains": ", ".join(allowed_domains)},
        )


# ---------------------------------------------------------------------------
# Security validators
# ---------------------------------------------------------------------------

def validate_password_strength(value: str) -> None:
    errors: list[str] = []
    if len(value) < 10:
        errors.append("At least 10 characters.")
    if not re.search(r"[A-Z]", value):
        errors.append("At least one uppercase letter.")
    if not re.search(r"[a-z]", value):
        errors.append("At least one lowercase letter.")
    if not re.search(r"\d", value):
        errors.append("At least one digit.")
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>?/\\|`~]", value):
        errors.append("At least one special character.")
    if errors:
        raise ValidationError(
            _("Password does not meet requirements: %(reasons)s"),
            params={"reasons": " ".join(errors)},
        )


def validate_no_common_passwords(value: str) -> None:
    COMMON = {
        "password", "password123", "123456", "qwerty", "admin",
        "letmein", "welcome", "monkey", "dragon", "master",
    }
    if value.lower() in COMMON:
        raise ValidationError(_("This password is too common."))


def validate_ip_address(value: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise ValidationError(_("Enter a valid IP address."))


def validate_ip_not_private(value: str) -> None:
    try:
        ip = ipaddress.ip_address(value)
        if ip.is_private:
            raise ValidationError(_("Private IP addresses are not allowed."))
    except ValueError:
        raise ValidationError(_("Enter a valid IP address."))


def validate_ip_list(values: list) -> None:
    if not isinstance(values, list):
        raise ValidationError(_("IP list must be a JSON array."))
    for ip in values:
        validate_ip_address(str(ip))


def validate_api_key_format(value: str) -> None:
    if len(value) < 32:
        raise ValidationError(_("API key must be at least 32 characters."))
    if not re.match(r"^[A-Za-z0-9_-]+$", value):
        raise ValidationError(_("API key must be URL-safe (letters, digits, - _)."))


def validate_hex_token(value: str, expected_length: int = 64) -> None:
    if not re.match(r"^[0-9a-f]+$", value.lower()):
        raise ValidationError(_("Enter a valid hexadecimal token."))
    if len(value) != expected_length:
        raise ValidationError(
            _("Token must be exactly %(n)d characters."),
            params={"n": expected_length},
        )


def validate_url_safe_token(value: str) -> None:
    if not re.match(r"^[A-Za-z0-9_-]+$", value):
        raise ValidationError(_("Token contains invalid characters."))


def validate_otp_format(value: str, digits: int = 6) -> None:
    if not value.isdigit() or len(value) != digits:
        raise ValidationError(
            _("OTP must be exactly %(n)d digits."), params={"n": digits}
        )


# ---------------------------------------------------------------------------
# File validators
# ---------------------------------------------------------------------------

class StrongPasswordValidator:
    """
    Django AUTH_PASSWORD_VALIDATORS-compatible validator.
    Enforces uppercase, lowercase, digit, and special-character requirements.
    """

    def __init__(
        self,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digits: bool = True,
        require_special: bool = True,
    ) -> None:
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_special = require_special

    def validate(self, password: str, user=None) -> None:
        errors: list[str] = []
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            errors.append("at least one uppercase letter (A-Z)")
        if self.require_lowercase and not re.search(r"[a-z]", password):
            errors.append("at least one lowercase letter (a-z)")
        if self.require_digits and not re.search(r"\d", password):
            errors.append("at least one digit (0-9)")
        if self.require_special and not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>?/\\|`~]", password):
            errors.append("at least one special character (!@#$%…)")
        if errors:
            raise ValidationError(
                _("Password must contain: %(reqs)s."),
                code="password_too_simple",
                params={"reqs": ", ".join(errors)},
            )

    def get_help_text(self) -> str:
        return _(
            "Your password must include at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character."
        )


def validate_upload_extension(file) -> None:
    from django.conf import settings
    allowed = getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", [])
    name = getattr(file, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if not ext or ext not in allowed:
        raise ValidationError(
            _("File type .%(ext)s is not allowed. Permitted: %(allowed)s"),
            params={"ext": ext or "(none)", "allowed": ", ".join(sorted(allowed))},
        )


def validate_file_size(file, max_mb: float = 10.0) -> None:
    max_bytes = int(max_mb * 1024 * 1024)
    size = getattr(file, "size", 0)
    if size > max_bytes:
        raise ValidationError(
            _("File size %(size)s exceeds the %(limit)s limit."),
            params={
                "size": f"{size / 1024 / 1024:.1f} MB",
                "limit": f"{max_mb:.0f} MB",
            },
        )


def validate_image_extension(filename: str) -> None:
    allowed = {"jpg", "jpeg", "png", "gif", "webp"}
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise ValidationError(
            _("Unsupported image format. Allowed: %(allowed)s"),
            params={"allowed": ", ".join(sorted(allowed))},
        )


def validate_document_extension(filename: str) -> None:
    allowed = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt"}
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise ValidationError(
            _("Unsupported document format. Allowed: %(allowed)s"),
            params={"allowed": ", ".join(sorted(allowed))},
        )


# ---------------------------------------------------------------------------
# Surveillance / domain validators
# ---------------------------------------------------------------------------

def validate_case_count(value: int) -> None:
    if value < 0:
        raise ValidationError(_("Case count cannot be negative."))
    if value > 100_000_000:
        raise ValidationError(_("Case count appears unrealistically high."))


def validate_incubation_period(value: float) -> None:
    if not (0 <= value <= 60):
        raise ValidationError(_("Incubation period must be between 0 and 60 days."))


def validate_alert_threshold(value: float) -> None:
    if not (0 < value <= 100):
        raise ValidationError(_("Alert threshold must be between 0 and 100."))


def validate_risk_score(value: float) -> None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Enter a valid number."))
    if not (0.0 <= f <= 1.0):
        raise ValidationError(_("Risk score must be between 0.0 and 1.0."))


def validate_dhis2_uid(value: str) -> None:
    if not re.match(r"^[A-Za-z][A-Za-z0-9]{10}$", value):
        raise ValidationError(_("Enter a valid DHIS2 UID (11 alphanumeric chars, starting with a letter)."))


def validate_icd_code(value: str) -> None:
    if not re.match(r"^[A-Z]\d{2}(\.\d{1,4})?$", value):
        raise ValidationError(_("Enter a valid ICD-10/11 code (e.g. A90, B01.0)."))