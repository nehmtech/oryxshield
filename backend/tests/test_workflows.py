"""Happy-path and state-machine tests for core operational workflows."""
import uuid
from datetime import date, timedelta

import pytest

from core.models import AuditLog, Location


@pytest.fixture
def region(db):
    return Location.objects.create(name="Khomas", code="NA-KH", location_type="REGION")


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    return api_client


# ---------------------------------------------------------------------------
# Response: activation + escalation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestResponseEscalation:
    @pytest.fixture
    def levels(self):
        from response.models import ResponseLevel
        return [
            ResponseLevel.objects.create(
                level=i, name=f"L{i}", description="d", risk_score_threshold=i * 20)
            for i in (1, 2, 3)
        ]

    @pytest.fixture
    def activation(self, levels, region):
        from response.models import ResponseActivation
        return ResponseActivation.objects.create(
            activation_code="ACT-1", response_level=levels[0], location=region, justification="test")

    def url(self, activation):
        return f"/api/v1/response/activations/{activation.id}/escalate/"

    def test_escalate_up(self, admin_client, activation, levels):
        r = admin_client.post(self.url(activation),
                              {"new_level_id": str(levels[2].id), "reason": "rapid community spread confirmed"}, format="json")
        assert r.status_code == 200, r.content
        activation.refresh_from_db()
        assert activation.response_level == levels[2] and activation.status == "ESCALATED"
        assert activation.escalation_history[-1]["to_level"] == 3

    def test_cannot_escalate_to_same_level(self, admin_client, activation, levels):
        r = admin_client.post(self.url(activation),
                              {"new_level_id": str(levels[0].id), "reason": "no real change here"}, format="json")
        assert r.status_code == 400

    def test_unknown_level_404_and_missing_fields_400(self, admin_client, activation):
        r = admin_client.post(self.url(activation),
                              {"new_level_id": str(uuid.uuid4()), "reason": "level does not exist"}, format="json")
        assert r.status_code == 404
        assert admin_client.post(self.url(activation), {}, format="json").status_code == 400

    def test_cannot_escalate_completed(self, admin_client, activation, levels):
        activation.status = "COMPLETED"
        activation.save()
        r = admin_client.post(self.url(activation),
                              {"new_level_id": str(levels[2].id), "reason": "already completed response"}, format="json")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Resources: procurement approval workflow
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProcurementWorkflow:
    @pytest.fixture
    def proc(self, region):
        from resources.models import Facility, ProcurementRequest
        fac = Facility.objects.create(
            name="Central Hospital", code="F1", facility_type="HOSPITAL", location=region)
        return ProcurementRequest.objects.create(
            request_number="PR-1", requesting_facility=fac,
            required_by_date=date.today() + timedelta(days=7), justification="stock out")

    def url(self, proc, action):
        return f"/api/v1/resources/procurement/{proc.id}/{action}/"

    def test_submit_approve(self, admin_client, admin_user, proc):
        assert admin_client.post(self.url(proc, "submit")).status_code == 200
        proc.refresh_from_db()
        assert proc.status == "SUBMITTED"
        assert admin_client.post(self.url(proc, "approve")).status_code == 200
        proc.refresh_from_db()
        # The post-approval Celery task (eager in tests) may advance APPROVED -> ORDERED.
        assert proc.status in ("APPROVED", "ORDERED") and proc.approved_by == admin_user
        assert AuditLog.objects.filter(
            action="APPROVE", model_name="ProcurementRequest", object_id=str(proc.id)).exists()

    def test_cannot_approve_draft(self, admin_client, proc):
        assert admin_client.post(self.url(proc, "approve")).status_code == 400

    def test_reject_requires_reason_then_blocks_approval(self, admin_client, proc):
        admin_client.post(self.url(proc, "submit"))
        assert admin_client.post(self.url(proc, "reject"), {}, format="json").status_code == 400
        r = admin_client.post(self.url(proc, "reject"), {"reason": "over budget"}, format="json")
        assert r.status_code == 200
        proc.refresh_from_db()
        assert proc.status == "REJECTED" and proc.rejection_reason == "over budget"
        assert admin_client.post(self.url(proc, "approve")).status_code == 400

    def test_cancel(self, admin_client, proc):
        assert admin_client.post(self.url(proc, "cancel")).status_code == 200
        proc.refresh_from_db()
        assert proc.status == "CANCELLED"
        assert admin_client.post(self.url(proc, "cancel")).status_code == 400


# ---------------------------------------------------------------------------
# Operations: contact-tracing case lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCaseLifecycle:
    @pytest.fixture
    def case(self, region):
        from operations.models import Case
        return Case.objects.create(
            case_id="C-1", patient_name="Test Patient", location=region,
            disease_code="A00", disease_name="Cholera")

    def test_resolve_recovered(self, admin_client, case):
        r = admin_client.post(f"/api/v1/operations/cases/{case.id}/resolve/",
                              {"outcome": "RECOVERED"}, format="json")
        assert r.status_code == 200
        case.refresh_from_db()
        assert case.status == "RECOVERED"
        assert AuditLog.objects.filter(model_name="Case", object_id=str(case.pk)).exists()

    def test_resolve_rejects_bad_outcome(self, admin_client, case):
        r = admin_client.post(f"/api/v1/operations/cases/{case.id}/resolve/",
                              {"outcome": "BANANA"}, format="json")
        assert r.status_code == 400
        case.refresh_from_db()
        assert case.status == "ACTIVE"

    def test_active_listing_excludes_resolved(self, admin_client, case):
        admin_client.post(f"/api/v1/operations/cases/{case.id}/resolve/",
                          {"outcome": "DECEASED"}, format="json")
        r = admin_client.get("/api/v1/operations/cases/active/")
        assert r.status_code == 200
        body = r.json()
        ids = [c["id"] for c in (body.get("results") if isinstance(body, dict) else body)]
        assert str(case.id) not in ids

    def test_contact_linked_to_case(self, admin_client, case, region):
        today = date.today().isoformat()
        r = admin_client.post("/api/v1/operations/contacts/", {
            "contact_id": "CT-1", "source_case": str(case.id), "contact_name": "Jane",
            "location": str(region.id), "contact_type": "HOUSEHOLD",
            "exposure_date": today, "last_contact_date": today,
        }, format="json")
        assert r.status_code in (200, 201), r.content


# ---------------------------------------------------------------------------
# Coordination: agency CRUD round-trip
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_agency_crud_roundtrip(admin_client):
    payload = {
        "name": "Ministry of Health", "acronym": "MOHSS", "agency_type": "GOVERNMENT",
        "primary_contact": "A", "contact_email": "a@example.org", "contact_phone": "+264811234567",
    }
    r = admin_client.post("/api/v1/coordination/agencies/", payload, format="json")
    assert r.status_code in (200, 201), r.content
    aid = r.json()["id"]
    r = admin_client.patch(f"/api/v1/coordination/agencies/{aid}/", {"acronym": "MHSS"}, format="json")
    assert r.status_code == 200
    assert admin_client.get(f"/api/v1/coordination/agencies/{aid}/").json()["acronym"] == "MHSS"
    assert admin_client.delete(f"/api/v1/coordination/agencies/{aid}/").status_code in (200, 204)
    assert admin_client.get(f"/api/v1/coordination/agencies/{aid}/").status_code == 404
