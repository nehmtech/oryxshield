"""
Risk calculation algorithms for the risk_assessment app.

Entry point: calculate_risk_for_location_disease(location_id, disease_code)
Returns a saved RiskScore instance or None if there is insufficient data.
"""
import logging
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Component weights — must sum to 1.0
# ---------------------------------------------------------------------------
_WEIGHTS = {
    "incidence": 0.25,
    "transmission": 0.25,
    "severity": 0.20,
    "vulnerability": 0.15,
    "capacity": 0.15,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def calculate_risk_for_location_disease(location_id: str, disease_code: str):
    """
    Compute and persist a RiskScore for the given (location, disease_code).

    Returns the saved RiskScore, or None when there is no health data for
    the past 7 days.
    """
    from core.models import Location
    from surveillance.models import HealthData
    from .models import RiskScore

    try:
        location = Location.objects.get(id=location_id)
    except Location.DoesNotExist:
        logger.warning("calculate_risk: location %s not found", location_id)
        return None

    week_ago = timezone.now() - timedelta(days=7)
    recent_data = HealthData.objects.filter(
        location=location,
        disease_code=disease_code,
        date_recorded__gte=week_ago,
        is_deleted=False,
    )

    if not recent_data.exists():
        logger.debug(
            "calculate_risk: no recent data for %s / %s",
            location_id, disease_code,
        )
        return None

    # ── component scores ─────────────────────────────────────────────────────
    incidence_score = _incidence_score(recent_data, location)
    transmission_score = _transmission_score(recent_data)
    severity_score = _severity_score(recent_data, disease_code)
    vulnerability_score = _vulnerability_score(location)
    capacity_score = _capacity_score(location)

    overall = (
        incidence_score * _WEIGHTS["incidence"]
        + transmission_score * _WEIGHTS["transmission"]
        + severity_score * _WEIGHTS["severity"]
        + vulnerability_score * _WEIGHTS["vulnerability"]
        + capacity_score * _WEIGHTS["capacity"]
    )
    overall = round(overall, 2)

    # ── epidemiological metrics ───────────────────────────────────────────────
    r_naught = _r_naught(recent_data)
    cfr = _case_fatality_rate(recent_data)
    attack_rate = _attack_rate(recent_data, location.population or 1_000)

    disease_name = recent_data.first().disease_name

    # Deactivate any previous active score for today to avoid ambiguity
    today = timezone.now().date()
    RiskScore.objects.filter(
        location=location,
        disease_code=disease_code,
        assessment_date=today,
        is_active=True,
        is_deleted=False,
    ).update(is_active=False)

    risk_score = RiskScore.objects.create(
        location=location,
        disease_code=disease_code,
        disease_name=disease_name,
        assessment_date=today,
        overall_score=overall,
        risk_level=_level(overall),
        incidence_score=round(incidence_score, 2),
        transmission_score=round(transmission_score, 2),
        severity_score=round(severity_score, 2),
        vulnerability_score=round(vulnerability_score, 2),
        capacity_score=round(capacity_score, 2),
        r_naught=r_naught,
        case_fatality_rate=cfr,
        attack_rate=attack_rate,
        population_at_risk=location.population or 0,
        confidence_level=_confidence(recent_data),
        is_active=True,
    )

    logger.info(
        "RiskScore created: %s/%s — %s (%s)",
        location.name, disease_code, risk_score.risk_level, overall,
    )
    return risk_score


# ---------------------------------------------------------------------------
# Component score functions
# ---------------------------------------------------------------------------

def _incidence_score(health_data, location) -> float:
    """Score 0–10 based on incidence rate per 100 k population."""
    population = max(location.population or 1_000, 1)
    rate = (health_data.count() / population) * 100_000
    if rate >= 100:
        return 10.0
    if rate >= 50:
        return 8.0
    if rate >= 20:
        return 6.0
    if rate >= 10:
        return 4.0
    if rate >= 5:
        return 2.0
    return 1.0


def _transmission_score(health_data) -> float:
    """Score 0–10 based on week-on-week growth rate."""
    daily = list(
        health_data.values("date_recorded__date")
        .annotate(count=Count("id"))
        .order_by("date_recorded__date")
        .values_list("count", flat=True)
    )
    if len(daily) < 2:
        return 0.0

    mid = len(daily) // 2
    first_half = sum(daily[:mid]) or 1
    second_half = sum(daily[mid:])
    growth = (second_half / first_half) - 1

    if growth >= 2.0:
        return 10.0
    if growth >= 1.0:
        return 8.0
    if growth >= 0.5:
        return 6.0
    if growth >= 0.2:
        return 4.0
    return 2.0


def _severity_score(health_data, disease_code: str) -> float:
    """Score 0–10 based on proportion of severe / critical cases."""
    total = health_data.count()
    if total == 0:
        return 5.0

    severe = health_data.filter(severity__in=["SEVERE", "CRITICAL"]).count()
    rate = severe / total

    if rate >= 0.5:
        return 10.0
    if rate >= 0.3:
        return 8.0
    if rate >= 0.1:
        return 6.0
    return 5.0


def _vulnerability_score(location) -> float:
    """Score 0–10 based on population size (proxy for vulnerability)."""
    score = 5.0
    if location.population:
        if location.population > 1_000_000:
            score += 2.0
        elif location.population > 100_000:
            score += 1.0
    return min(score, 10.0)


def _capacity_score(location) -> float:  # noqa: ARG001
    """
    Score 0–10 reflecting healthcare pressure.

    Higher score = worse capacity (more stressed system). Returns a neutral
    midpoint until real capacity data is integrated.
    """
    return 5.0


# ---------------------------------------------------------------------------
# Epidemiological metric helpers
# ---------------------------------------------------------------------------

def _r_naught(health_data):
    """Estimate R₀ from a 3-day rolling growth rate. Returns None if data is sparse."""
    daily = list(
        health_data.values("date_recorded__date")
        .annotate(count=Count("id"))
        .order_by("date_recorded__date")
        .values_list("count", flat=True)
    )
    if len(daily) < 7:
        return None

    recent = sum(daily[-3:])
    previous = sum(daily[-6:-3])
    if previous == 0:
        return None

    return round(recent / previous, 2)


def _case_fatality_rate(health_data):
    """CFR as a percentage. Returns None if there are no cases."""
    total = health_data.count()
    if total == 0:
        return None
    deaths = health_data.filter(outcome="DEATH").count()
    return round((deaths / total) * 100, 2)


def _attack_rate(health_data, population: int):
    """Attack rate as a percentage. Returns None for zero population."""
    if population == 0:
        return None
    return round((health_data.count() / population) * 100, 2)


def _confidence(health_data) -> float:
    """Statistical confidence 0–100 based on record volume."""
    n = health_data.count()
    if n >= 100:
        return 95.0
    if n >= 50:
        return 85.0
    if n >= 20:
        return 75.0
    if n >= 10:
        return 60.0
    return 40.0


# ---------------------------------------------------------------------------
# Derived classification helpers
# ---------------------------------------------------------------------------

def _level(score: float) -> str:
    """Map numeric score to RISK_LEVEL choice."""
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.5:
        return "VERY_HIGH"
    if score >= 6.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score >= 2.0:
        return "LOW"
    return "VERY_LOW"


def calculate_threat_level(risk_score) -> dict:
    """
    Derive threat-classification data from a RiskScore instance.

    Returns a dict suitable for ThreatClassification.objects.update_or_create().
    """
    score = float(risk_score.overall_score)

    if score >= 9.0:
        level = "EXTREME"
    elif score >= 7.5:
        level = "SEVERE"
    elif score >= 6.0:
        level = "HIGH"
    elif score >= 4.0:
        level = "MODERATE"
    else:
        level = "LOW"

    r0 = float(risk_score.r_naught) if risk_score.r_naught else 0.0
    pandemic_potential = r0 > 2.0 and score >= 7.0

    justification = f"Derived from risk score {score:.2f} ({risk_score.risk_level})."
    if pandemic_potential:
        justification += f" R₀ = {r0:.2f} indicates high pandemic potential."

    return {
        "level": level,
        "score": score,
        "pandemic_potential": pandemic_potential,
        "justification": justification,
    }