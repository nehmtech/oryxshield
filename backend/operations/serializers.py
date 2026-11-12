"""
Serializers for operations app.
"""
from rest_framework import serializers
from django.utils import timezone
from .models import (
    Case, Contact, ContactMonitoring,
    TestingCenter, TestingAppointment,
    VaccinationCampaign, VaccinationRecord,
    QuarantineFacility, QuarantineRecord,
)


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------

class CaseListSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)

    class Meta:
        model = Case
        fields = [
            'id', 'case_id', 'patient_name', 'patient_age', 'patient_gender',
            'disease_code', 'disease_name', 'classification', 'status',
            'location', 'location_name', 'symptom_onset_date',
            'is_isolated', 'assigned_to_name', 'created_at',
        ]


class CaseSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    contacts_count = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_contacts_count(self, obj):
        return obj.contacts.filter(is_deleted=False).count()

    def validate_patient_age(self, value):
        if value is not None and (value < 0 or value > 150):
            raise serializers.ValidationError("Age must be between 0 and 150.")
        return value

    def validate(self, data):
        onset = data.get('symptom_onset_date')
        diagnosis = data.get('diagnosis_date')
        if onset and diagnosis and diagnosis < onset:
            raise serializers.ValidationError(
                "Diagnosis date cannot precede symptom onset date."
            )
        return data


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

class ContactListSerializer(serializers.ModelSerializer):
    source_case_id = serializers.CharField(source='source_case.case_id', read_only=True)

    class Meta:
        model = Contact
        fields = [
            'id', 'contact_id', 'contact_name', 'contact_type', 'status',
            'source_case', 'source_case_id', 'exposure_date',
            'is_quarantined', 'monitoring_end_date',
        ]


class ContactSerializer(serializers.ModelSerializer):
    source_case_id = serializers.CharField(source='source_case.case_id', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    days_remaining_in_monitoring = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_days_remaining_in_monitoring(self, obj):
        if obj.monitoring_end_date:
            delta = obj.monitoring_end_date - timezone.now().date()
            return max(0, delta.days)
        return None

    def validate(self, data):
        exposure = data.get('exposure_date')
        last_contact = data.get('last_contact_date')
        if exposure and last_contact and last_contact < exposure:
            raise serializers.ValidationError(
                "Last contact date cannot precede exposure date."
            )
        return data


# ---------------------------------------------------------------------------
# Contact Monitoring
# ---------------------------------------------------------------------------

class ContactMonitoringSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source='contact.contact_name', read_only=True)
    monitored_by_name = serializers.CharField(source='monitored_by.username', read_only=True)

    class Meta:
        model = ContactMonitoring
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        contact = data.get('contact') or (self.instance and self.instance.contact)
        date = data.get('monitoring_date') or (self.instance and self.instance.monitoring_date)
        if contact and date:
            qs = ContactMonitoring.objects.filter(
                contact=contact, monitoring_date=date
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "A monitoring record for this contact on this date already exists."
                )
        return data


# ---------------------------------------------------------------------------
# Testing Center
# ---------------------------------------------------------------------------

class TestingCenterSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    available_slots = serializers.IntegerField(read_only=True)
    is_at_capacity = serializers.BooleanField(read_only=True)

    class Meta:
        model = TestingCenter
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_daily_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Daily capacity must be at least 1.")
        return value


# ---------------------------------------------------------------------------
# Testing Appointment
# ---------------------------------------------------------------------------

class TestingAppointmentSerializer(serializers.ModelSerializer):
    center_name = serializers.CharField(source='testing_center.name', read_only=True)
    case_ref = serializers.CharField(source='case.case_id', read_only=True)
    contact_ref = serializers.CharField(source='contact.contact_id', read_only=True)

    class Meta:
        model = TestingAppointment
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        center = data.get('testing_center') or (
            self.instance and self.instance.testing_center
        )
        date = data.get('appointment_date') or (
            self.instance and self.instance.appointment_date
        )
        if center and date and center.is_at_capacity:
            raise serializers.ValidationError(
                f"Testing center {center.name} is at capacity for {date}."
            )
        return data


# ---------------------------------------------------------------------------
# Vaccination Campaign
# ---------------------------------------------------------------------------

class VaccinationCampaignSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(
        source='campaign_manager.username', read_only=True
    )
    coverage_rate = serializers.FloatField(read_only=True)
    target_location_names = serializers.SerializerMethodField()

    class Meta:
        model = VaccinationCampaign
        fields = '__all__'
        read_only_fields = [
            'created_at', 'updated_at',
            'doses_administered', 'people_vaccinated',
        ]

    def get_target_location_names(self, obj):
        return list(obj.target_locations.values_list('name', flat=True))

    def validate(self, data):
        start = data.get('start_date') or (self.instance and self.instance.start_date)
        end = data.get('end_date') or (self.instance and self.instance.end_date)
        if start and end and end <= start:
            raise serializers.ValidationError(
                "End date must be after start date."
            )
        return data


# ---------------------------------------------------------------------------
# Vaccination Record
# ---------------------------------------------------------------------------

class VaccinationRecordSerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    administered_by_name = serializers.CharField(
        source='administered_by.username', read_only=True
    )

    class Meta:
        model = VaccinationRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_dose_number(self, value):
        if value < 1:
            raise serializers.ValidationError("Dose number must be at least 1.")
        return value

    def validate_patient_age(self, value):
        if value < 0 or value > 150:
            raise serializers.ValidationError("Age must be between 0 and 150.")
        return value


# ---------------------------------------------------------------------------
# Quarantine Facility
# ---------------------------------------------------------------------------

class QuarantineFacilitySerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    occupancy_rate = serializers.FloatField(read_only=True)
    available_beds = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)

    class Meta:
        model = QuarantineFacility
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'current_occupancy']

    def validate_total_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Total capacity must be at least 1.")
        return value


# ---------------------------------------------------------------------------
# Quarantine Record
# ---------------------------------------------------------------------------

class QuarantineRecordSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    case_ref = serializers.CharField(source='case.case_id', read_only=True)
    contact_ref = serializers.CharField(source='contact.contact_id', read_only=True)
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = QuarantineRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'actual_release_date']

    def get_days_remaining(self, obj):
        if obj.expected_release_date and obj.status == QuarantineRecord.STATUS_IN_QUARANTINE:
            delta = obj.expected_release_date - timezone.now().date()
            return max(0, delta.days)
        return None

    def validate(self, data):
        admission = data.get('admission_date') or (
            self.instance and self.instance.admission_date
        )
        release = data.get('expected_release_date') or (
            self.instance and self.instance.expected_release_date
        )
        if admission and release and release <= admission:
            raise serializers.ValidationError(
                "Expected release date must be after admission date."
            )
        facility = data.get('facility') or (self.instance and self.instance.facility)
        if facility and not self.instance and facility.is_full:
            raise serializers.ValidationError(
                f"Facility {facility.name} is at full capacity."
            )
        return data


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class OperationsDashboardSerializer(serializers.Serializer):
    active_cases = serializers.IntegerField()
    confirmed_cases = serializers.IntegerField()
    contacts_under_monitoring = serializers.IntegerField()
    symptomatic_contacts = serializers.IntegerField()
    quarantined_individuals = serializers.IntegerField()
    tests_today = serializers.IntegerField()
    positive_tests_today = serializers.IntegerField()
    vaccinations_today = serializers.IntegerField()
    quarantine_completions_today = serializers.IntegerField()
    facilities_at_capacity = serializers.IntegerField()