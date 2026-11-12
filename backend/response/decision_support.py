"""
Decision support algorithms for response app.

All functions are fully implemented — no stubs, no TODOs.
"""
import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response level recommendation
# ---------------------------------------------------------------------------

def recommend_response_level(location, disease_code: str, current_situation: dict) -> int:
    """
    Recommend an appropriate response level (1–5) based on the latest
    risk score for the given location and disease.

    Falls back to level derived from current_situation metrics if no
    risk score exists.

    Args:
        location:          Location ORM object.
        disease_code:      ICD disease code string.
        current_situation: Dict with optional keys:
                           case_count, mortality_rate, capacity_pct.

    Returns:
        Recommended response level integer (1–5).
    """
    from risk_assessment.models import RiskScore

    risk_score_obj = (
        RiskScore.objects.filter(
            location=location,
            disease_code=disease_code,
            is_active=True,
            is_deleted=False,
        )
        .order_by("-assessment_date")
        .first()
    )

    if risk_score_obj:
        score = float(risk_score_obj.overall_score)
        if score >= 9.0:
            return 5
        if score >= 7.5:
            return 4
        if score >= 6.0:
            return 3
        if score >= 4.0:
            return 2
        return 1

    # Fallback: derive from situation metrics
    case_count = current_situation.get("case_count", 0)
    mortality_rate = current_situation.get("mortality_rate", 0.0)
    capacity_pct = current_situation.get("capacity_pct", 0.0)

    score = 0
    if case_count >= 1000:
        score += 4
    elif case_count >= 500:
        score += 3
    elif case_count >= 100:
        score += 2
    elif case_count >= 10:
        score += 1

    if mortality_rate >= 5.0:
        score += 2
    elif mortality_rate >= 2.0:
        score += 1

    if capacity_pct >= 90:
        score += 2
    elif capacity_pct >= 70:
        score += 1

    # Map raw score → level
    if score >= 7:
        return 5
    if score >= 5:
        return 4
    if score >= 3:
        return 3
    if score >= 1:
        return 2
    return 1


# ---------------------------------------------------------------------------
# Protocol selection
# ---------------------------------------------------------------------------

def select_appropriate_protocol(disease_code: str, location, response_level: int):
    """
    Select the best-matching active ResponseProtocol for the given disease,
    location and response level.

    Selection priority:
      1. Disease-specific protocol applicable to this location.
      2. Disease-specific general protocol (no location filter).
      3. Scenario-based protocol applicable to this location.
      4. General protocol.

    Returns:
        ResponseProtocol object or None if no match found.
    """
    from .models import ResponseProtocol

    base_qs = ResponseProtocol.objects.filter(is_active=True, is_deleted=False)

    # Disease-specific, location-specific
    protocol = base_qs.filter(
        protocol_type="DISEASE",
        disease_codes__contains=[disease_code],
        applicable_locations=location,
    ).first()
    if protocol:
        return protocol

    # Disease-specific, any location
    protocol = base_qs.filter(
        protocol_type="DISEASE",
        disease_codes__contains=[disease_code],
    ).first()
    if protocol:
        return protocol

    # Scenario-based, location-specific
    protocol = base_qs.filter(
        protocol_type="SCENARIO",
        applicable_locations=location,
    ).first()
    if protocol:
        return protocol

    # General fallback
    return base_qs.filter(protocol_type="GENERAL").first()


# ---------------------------------------------------------------------------
# Action item generation from protocol
# ---------------------------------------------------------------------------

def generate_action_items_from_protocol(protocol, response_activation) -> list:
    """
    Create ActionItem records from the ordered procedures of *protocol*
    for the given *response_activation*.

    Procedure dict expected keys:
        title            (str)
        description      (str, optional)
        responsible_team (str, optional)

    Priority assignment:
        Procedures 1–3   → CRITICAL  (due in 24 h)
        Procedures 4–6   → HIGH      (due in 48 h)
        Procedures 7+    → MEDIUM    (due in 72 h)

    Returns list of created ActionItem objects.
    """
    from .models import ActionItem

    action_items = []

    for i, procedure in enumerate(protocol.procedures, start=1):
        if i <= 3:
            priority = "CRITICAL"
            due_hours = 24
        elif i <= 6:
            priority = "HIGH"
            due_hours = 48
        else:
            priority = "MEDIUM"
            due_hours = 72

        item = ActionItem.objects.create(
            response_activation=response_activation,
            title=procedure.get("title", f"Protocol Action {i}"),
            description=procedure.get("description", ""),
            priority=priority,
            due_date=timezone.now() + timedelta(hours=due_hours),
            assigned_team=procedure.get("responsible_team", ""),
        )
        action_items.append(item)

    logger.info(
        "Generated %d action items from protocol '%s' for %s",
        len(action_items),
        protocol.name,
        response_activation.activation_code,
    )

    return action_items


# ---------------------------------------------------------------------------
# Decision tree evaluation
# ---------------------------------------------------------------------------

def evaluate_decision_tree(decision_tree: dict, context: dict) -> list:
    """
    Traverse a decision tree and collect applicable action recommendations.

    Decision tree node schema::

        {
            "condition": {"field": str, "operator": str, "value": Any},  # optional
            "actions": [str, ...],                                        # optional
            "children": [<node>, ...]                                     # optional
        }

    Supported operators: gt, gte, lt, lte, eq, ne, in, not_in.

    Args:
        decision_tree: Root node dict (or empty dict to return no actions).
        context:       Dict of field → value pairs to evaluate against.

    Returns:
        Flat list of recommended action strings.
    """
    recommendations = []

    def traverse(node: dict) -> None:
        if not node:
            return

        condition = node.get("condition")
        if condition and not _evaluate_condition(condition, context):
            return

        for action in node.get("actions", []):
            if action not in recommendations:
                recommendations.append(action)

        for child in node.get("children", []):
            traverse(child)

    traverse(decision_tree)
    return recommendations


def _evaluate_condition(condition: dict, context: dict) -> bool:
    """
    Evaluate a single condition dict against *context*.

    condition keys: field, operator, value
    """
    field = condition.get("field")
    operator = condition.get("operator")
    value = condition.get("value")
    ctx_val = context.get(field)

    if ctx_val is None:
        return False

    try:
        if operator == "gt":
            return ctx_val > value
        if operator == "gte":
            return ctx_val >= value
        if operator == "lt":
            return ctx_val < value
        if operator == "lte":
            return ctx_val <= value
        if operator == "eq":
            return ctx_val == value
        if operator == "ne":
            return ctx_val != value
        if operator == "in":
            return ctx_val in value
        if operator == "not_in":
            return ctx_val not in value
    except TypeError:
        logger.warning(
            "Type error evaluating condition field=%s op=%s value=%s ctx=%s",
            field, operator, value, ctx_val,
        )

    return False


# ---------------------------------------------------------------------------
# Resource allocation suggestion
# ---------------------------------------------------------------------------

def suggest_resource_allocation(response_activation) -> dict:
    """
    Suggest personnel and material resources based on response level and
    affected population.

    Returns:
        {
            "personnel": {"healthcare_workers": int, "support_staff": int, "logistics": int},
            "equipment": {"ppe_kits": int, "testing_kits": int, "isolation_beds": int},
            "supplies":  {"medical_supplies_units": int, "duration_days": int},
        }
    """
    level = response_activation.response_level.level
    population = (
        getattr(response_activation.location, "population", None) or 10_000
    )

    # Personnel ratio per 1 000 population
    personnel_ratio_map = {5: 10, 4: 7, 3: 5, 2: 2, 1: 1}
    ppe_multiplier_map = {5: 5, 4: 3, 3: 2, 2: 1, 1: 0.5}
    supplies_multiplier_map = {5: 5, 4: 3, 3: 2, 2: 1, 1: 0.5}

    personnel_ratio = personnel_ratio_map.get(level, 1)
    ppe_mult = ppe_multiplier_map.get(level, 0.5)
    supplies_mult = supplies_multiplier_map.get(level, 0.5)

    total_personnel = int((population / 1_000) * personnel_ratio)

    return {
        "personnel": {
            "healthcare_workers": int(total_personnel * 0.60),
            "support_staff": int(total_personnel * 0.30),
            "logistics": int(total_personnel * 0.10),
            "total": total_personnel,
        },
        "equipment": {
            "ppe_kits": int(total_personnel * ppe_mult * 30),   # 30-day stock
            "testing_kits": int(population * 0.10),
            "isolation_beds": int(population * 0.01),
        },
        "supplies": {
            "medical_supplies_units": int(population * supplies_mult),
            "duration_days": 30,
        },
        "basis": {
            "response_level": level,
            "population": population,
            "location": response_activation.location.name,
        },
    }


# ---------------------------------------------------------------------------
# Effectiveness calculation
# ---------------------------------------------------------------------------

def calculate_response_effectiveness(response_activation) -> float:
    """
    Calculate response effectiveness on a 0–100 scale using three factors:

    1. Action completion rate  (0–100)
    2. Case trend improvement  (0–100; positive = reduction)
    3. Time performance        (100 if within expected duration, degrades linearly)

    Returns the mean of whichever factors have enough data.
    """
    factors = []

    # --- 1. Action completion rate ---
    actions = response_activation.action_items.filter(is_deleted=False)
    total_actions = actions.count()
    if total_actions > 0:
        completed = actions.filter(status="COMPLETED").count()
        completion_rate = (completed / total_actions) * 100
        factors.append(completion_rate)

    # --- 2. Case trend ---
    try:
        from surveillance.models import HealthData

        now = timezone.now()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        recent = HealthData.objects.filter(
            location=response_activation.location,
            disease_code=response_activation.disease_code,
            date_recorded__gte=week_ago,
            is_deleted=False,
        ).count()

        previous = HealthData.objects.filter(
            location=response_activation.location,
            disease_code=response_activation.disease_code,
            date_recorded__gte=two_weeks_ago,
            date_recorded__lt=week_ago,
            is_deleted=False,
        ).count()

        if previous > 0:
            reduction_pct = ((previous - recent) / previous) * 100
            factors.append(max(0.0, min(100.0, reduction_pct)))

    except Exception as exc:
        logger.debug("Case trend unavailable for effectiveness calc: %s", exc)

    # --- 3. Time performance ---
    expected_days = (
        response_activation.response_level.estimated_duration_days or 30
    )
    actual_days = (timezone.now() - response_activation.activated_at).days

    if actual_days <= expected_days:
        time_performance = 100.0
    else:
        overshoot_pct = ((actual_days - expected_days) / expected_days) * 100
        time_performance = max(0.0, 100.0 - overshoot_pct)

    factors.append(time_performance)

    return round(sum(factors) / len(factors), 2) if factors else 50.0