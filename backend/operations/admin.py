"""Admin configuration for operations app."""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Case, Contact, ContactMonitoring,
    TestingCenter, TestingAppointment,
    VaccinationCampaign, VaccinationRecord,
    QuarantineFacility, QuarantineRecord,
)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = [
        'case_id', 'patient_name', 'disease_name',
        'classification', 'status', 'location', 'is_isolated', 'created_at',
    ]
    list_filter = ['classification', 'status', 'is_isolated', 'disease_code']
    search_fields = ['case_id', 'patient_name', 'patient_id_number']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    raw_id_fields = ['location', 'assigned_to', 'health_data']


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = [
        'contact_id', 'contact_name', 'source_case',
        'contact_type', 'status', 'is_quarantined', 'monitoring_end_date',
    ]
    list_filter = ['status', 'contact_type', 'is_quarantined']
    search_fields = ['contact_id', 'contact_name', 'contact_phone']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['source_case', 'location', 'assigned_to', 'became_case']


@admin.register(ContactMonitoring)
class ContactMonitoringAdmin(admin.ModelAdmin):
    list_display = [
        'contact', 'monitoring_date', 'has_symptoms',
        'temperature', 'is_reachable', 'is_compliant',
    ]
    list_filter = ['has_symptoms', 'is_compliant', 'monitoring_date']
    raw_id_fields = ['contact', 'monitored_by']
    date_hierarchy = 'monitoring_date'


@admin.register(TestingCenter)
class TestingCenterAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'location', 'daily_capacity',
        'current_load', 'is_operational',
    ]
    list_filter = ['is_operational', 'location']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']

    def capacity_bar(self, obj):
        pct = int((obj.current_load / obj.daily_capacity) * 100) if obj.daily_capacity else 0
        colour = 'green' if pct < 70 else 'orange' if pct < 90 else 'red'
        return format_html(
            '<div style="background:{};width:{}%;height:12px;border-radius:3px"></div>{}%',
            colour, pct, pct
        )
    capacity_bar.short_description = 'Load'


@admin.register(TestingAppointment)
class TestingAppointmentAdmin(admin.ModelAdmin):
    list_display = [
        'appointment_id', 'patient_name', 'testing_center',
        'appointment_date', 'appointment_time', 'status', 'result',
    ]
    list_filter = ['status', 'result', 'appointment_date']
    search_fields = ['appointment_id', 'patient_name', 'patient_id_number']
    date_hierarchy = 'appointment_date'
    raw_id_fields = ['testing_center', 'case', 'contact']


@admin.register(VaccinationCampaign)
class VaccinationCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'campaign_code', 'vaccine_name', 'status',
        'start_date', 'end_date', 'people_vaccinated', 'target_population',
    ]
    list_filter = ['status']
    search_fields = ['name', 'campaign_code']
    readonly_fields = ['doses_administered', 'people_vaccinated', 'created_at', 'updated_at']
    filter_horizontal = ['target_locations']


@admin.register(VaccinationRecord)
class VaccinationRecordAdmin(admin.ModelAdmin):
    list_display = [
        'record_id', 'patient_name', 'vaccine_name',
        'dose_number', 'vaccination_date', 'adverse_event_reported',
    ]
    list_filter = ['dose_number', 'vaccination_date', 'adverse_event_reported']
    search_fields = ['record_id', 'patient_name', 'patient_id_number']
    date_hierarchy = 'vaccination_date'
    raw_id_fields = ['campaign', 'location', 'administered_by']


@admin.register(QuarantineFacility)
class QuarantineFacilityAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'facility_type', 'location',
        'total_capacity', 'current_occupancy', 'is_operational',
    ]
    list_filter = ['facility_type', 'is_operational']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(QuarantineRecord)
class QuarantineRecordAdmin(admin.ModelAdmin):
    list_display = [
        'record_id', 'individual_name', 'facility',
        'status', 'admission_date', 'expected_release_date',
    ]
    list_filter = ['status', 'facility']
    search_fields = ['record_id', 'individual_name', 'individual_id_number']
    date_hierarchy = 'admission_date'
    raw_id_fields = ['facility', 'case', 'contact']