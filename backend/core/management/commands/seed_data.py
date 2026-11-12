"""
seed_data — OryxShield Demo Data Generator
====================================================
Company : NEHMTECH INNOVATIONS LIMITED
Author  : Nehemiah

Populates the database with realistic synthetic/mock data across all 13 apps
for demo, development, and testing purposes.

Usage:
    python manage.py seed_data               # seed everything (idempotent)
    python manage.py seed_data --flush       # wipe app data then re-seed
    python manage.py seed_data --app core    # seed only one app
"""

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone


def rand_decimal(lo, hi, places=2):
    return round(random.uniform(lo, hi), places)


def days_ago(n):
    return timezone.now() - timedelta(days=n)


class Command(BaseCommand):
    help = "Seed the database with synthetic demo data for all OryxShield apps."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true",
            help="Delete existing app data before seeding.")
        parser.add_argument("--app", type=str, default="all",
            help="Seed only a specific app.")

    def handle(self, *args, **options):
        self.flush = options["flush"]
        self.app   = options["app"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n+==================================+\n"
            "|  ORYXSHIELD -- SEED DATA  |\n"
            "+==================================+\n"
        ))

        if self.flush:
            self._flush()

        targets = [self.app] if self.app != "all" else [
            "core", "surveillance", "risk", "response",
            "coordination", "resources", "communications",
            "analytics", "operations", "integrations",
            "triggers_and_quality",
        ]

        for t in targets:
            fn = getattr(self, f"_seed_{t}", None)
            if fn:
                self.stdout.write(f"\n  Seeding {t}...")
                try:
                    fn()
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"  ERROR in {t}: {exc}"))
            else:
                self.stdout.write(self.style.WARNING(f"  Unknown app: {t} — skipped."))

        self.stdout.write(self.style.SUCCESS("\n  Seeding complete!\n"))

    # ─── flush ───────────────────────────────────────────────────────────────

    def _flush(self):
        self.stdout.write(self.style.WARNING("  Flushing existing data..."))
        _models_to_flush = []
        try:
            from operations.models import (
                Case, Contact, ContactMonitoring, TestingCenter, TestingAppointment,
                VaccinationCampaign, QuarantineFacility,
            )
            _models_to_flush.extend([
                TestingAppointment, ContactMonitoring, Contact, Case,
                QuarantineFacility, VaccinationCampaign, TestingCenter,
            ])
        except Exception:
            pass
        try:
            from analytics.models import (
                EpidemiologicalModel, SpatialAnalysis, TimeSeriesAnalysis,
                StatisticalReport, Dashboard,
            )
            _models_to_flush.extend([
                StatisticalReport, EpidemiologicalModel, SpatialAnalysis,
                TimeSeriesAnalysis, Dashboard,
            ])
        except Exception:
            pass
        try:
            from communications.models import Campaign, MessageTemplate
            _models_to_flush.extend([Campaign, MessageTemplate])
        except Exception:
            pass
        try:
            from resources.models import (
                ProcurementRequest, ProcurementItem, Inventory, ResourceItem,
                Facility, ResourceCategory, Supplier, StockMovement, DemandForecast,
            )
            _models_to_flush.extend([
                DemandForecast, ProcurementItem, ProcurementRequest, StockMovement,
                Inventory, ResourceItem, Facility, Supplier, ResourceCategory,
            ])
        except Exception:
            pass
        try:
            from coordination.models import Meeting, Task, TeamMembership, Team, Agency
            _models_to_flush.extend([Meeting, Task, TeamMembership, Team, Agency])
        except Exception:
            pass
        try:
            from response.models import (
                DecisionLog, ActionItem, ResponseActivation, ResponseProtocol, ResponseLevel,
            )
            _models_to_flush.extend([
                DecisionLog, ActionItem, ResponseActivation, ResponseProtocol, ResponseLevel,
            ])
        except Exception:
            pass
        try:
            from risk_assessment.models import Alert, RiskScore, Threshold, ThreatClassification
            _models_to_flush.extend([Alert, RiskScore, Threshold, ThreatClassification])
        except Exception:
            pass
        try:
            from surveillance.models import (
                AnomalyDetection, Hotspot, CaseCluster, HealthData,
                DataSource, DiseaseProfile, SurveillanceReport,
            )
            _models_to_flush.extend([
                AnomalyDetection, Hotspot, CaseCluster, HealthData,
                DataSource, DiseaseProfile, SurveillanceReport,
            ])
        except Exception:
            pass
        for model in _models_to_flush:
            try:
                count = model.objects.all().delete()[0]
                self.stdout.write(f"    Deleted {count} {model.__name__} records")
            except Exception:
                pass

    # =========================================================================
    # 1. CORE
    # =========================================================================

    def _seed_core(self):
        from core.models import Location, Notification, SystemConfiguration

        # ── Users ──────────────────────────────────────────────────────────────
        users_spec = [
            dict(username="admin",        email="admin@oryxshield.gov.na",    first_name="Admin",   last_name="User",     is_superuser=True,  is_staff=True),
            dict(username="analyst1",     email="analyst1@oryxshield.gov.na", first_name="Ndapandula", last_name="Amupolo",    is_superuser=False, is_staff=False),
            dict(username="coordinator1", email="coord1@oryxshield.gov.na",   first_name="Johannes",   last_name="Shikongo",   is_superuser=False, is_staff=False),
            dict(username="field1",       email="field1@oryxshield.gov.na",   first_name="Maria",      last_name="Nghifindaka",is_superuser=False, is_staff=False),
            dict(username="analyst2",     email="analyst2@oryxshield.gov.na", first_name="Daniel",     last_name="Hamukwaya",  is_superuser=False, is_staff=False),
            dict(username="coordinator2", email="coord2@oryxshield.gov.na",   first_name="Selma",      last_name="Nakamhela",  is_superuser=False, is_staff=False),
        ]
        # ── Role Groups ────────────────────────────────────────────────────────
        role_group_names = ["analyst", "coordinator", "field_officer"]
        self.role_groups = {}
        for gname in role_group_names:
            grp, _ = Group.objects.get_or_create(name=gname)
            self.role_groups[gname] = grp
        self.stdout.write(f"    Groups: {list(self.role_groups.keys())}")

        # Role → group assignments for seeded users
        role_assignments = {
            "admin":        None,           # superuser, no group needed
            "analyst1":     "analyst",
            "coordinator1": "coordinator",
            "field1":       "field_officer",
            "analyst2":     "analyst",
            "coordinator2": "coordinator",
        }

        self.users = []
        for spec in users_spec:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={**spec},
            )
            if created:
                user.set_password("OryxShield@2026!")
                user.save()

            # Always ensure correct group assignment (idempotent)
            grp_name = role_assignments.get(spec["username"])
            # Remove from all role groups first
            user.groups.remove(*self.role_groups.values())
            if grp_name:
                user.groups.add(self.role_groups[grp_name])

            self.users.append(user)
        self.admin_user = self.users[0]
        self.stdout.write(f"    Users: {len(self.users)}")

        # ── Locations ──────────────────────────────────────────────────────────
        locs_spec = [
            dict(name="Namibia",         code="NA",       location_type="COUNTRY",         latitude=-22.5609, longitude=17.0658, population=2600000),
            dict(name="Uganda",        code="UG",       location_type="COUNTRY",         latitude=1.3733,  longitude=32.2903, population=49000000),
            dict(name="Tanzania",      code="TZ",       location_type="COUNTRY",         latitude=-6.3690, longitude=34.8888, population=63000000),
            dict(name="Ethiopia",      code="ET",       location_type="COUNTRY",         latitude=9.1450,  longitude=40.4897, population=128000000),
            dict(name="Rwanda",        code="RW",       location_type="COUNTRY",         latitude=-1.9403, longitude=29.8739, population=1500000),
            dict(name="Nigeria",       code="NG",       location_type="COUNTRY",         latitude=9.0820,  longitude=8.6753,  population=225000000),
            dict(name="Ghana",         code="GH",       location_type="COUNTRY",         latitude=7.9465,  longitude=-1.0232, population=34000000),
            dict(name="South Africa",  code="ZA",       location_type="COUNTRY",         latitude=-30.559, longitude=22.9375, population=60000000),
            dict(name="Khomas Region",        code="NA-KHO",  location_type="REGION", latitude=-22.5609, longitude=17.0658,  population=342000),
            dict(name="Erongo Region",        code="NA-ERO",  location_type="REGION", latitude=-22.5667, longitude=14.5308,  population=150000),
            dict(name="Oshana Region",        code="NA-OSH",  location_type="REGION", latitude=-17.7817, longitude=15.6994,  population=170000),
            dict(name="Otjozondjupa Region",  code="NA-OTJ",  location_type="REGION", latitude=-20.4613, longitude=16.6446,  population=145000),
            dict(name="Hardap Region",        code="NA-HAR",  location_type="REGION", latitude=-24.6333, longitude=17.9833,  population=79000),
            dict(name="//Karas Region",       code="NA-KAR",  location_type="REGION", latitude=-26.5831, longitude=18.1272,  population=77000),
            dict(name="Kavango East Region",  code="NA-KVE",  location_type="REGION", latitude=-17.9333, longitude=19.7667,  population=136000),
            dict(name="Kavango West Region",  code="NA-KVW",  location_type="REGION", latitude=-17.6333, longitude=18.6167,  population=107000),
            dict(name="Kunene Region",        code="NA-KUN",  location_type="REGION", latitude=-18.0600, longitude=13.8400,  population=86000),
            dict(name="Ohangwena Region",     code="NA-OHW",  location_type="REGION", latitude=-17.4667, longitude=16.3500,  population=245000),
            dict(name="Omaheke Region",       code="NA-OMH",  location_type="REGION", latitude=-22.4500, longitude=18.9667,  population=71000),
            dict(name="Omusati Region",       code="NA-OMS",  location_type="REGION", latitude=-17.4667, longitude=15.0000,  population=243000),
            dict(name="Oshikoto Region",      code="NA-OKT",  location_type="REGION", latitude=-19.2167, longitude=17.7167,  population=181000),
            dict(name="Zambezi Region",       code="NA-ZAM",  location_type="REGION", latitude=-17.5000, longitude=24.2667,  population=90000),
            dict(name="Kampala District", code="UG-KLA",location_type="REGION",          latitude=0.3476,  longitude=32.5825, population=3600000),
            dict(name="Dar es Salaam", code="TZ-DAR",   location_type="REGION",          latitude=-6.7924, longitude=39.2083, population=7400000),
            dict(name="Addis Ababa",   code="ET-AA",    location_type="REGION",          latitude=9.0320,  longitude=38.7469, population=5000000),
            dict(name="Windhoek West", code="NA-KHO-WW",location_type="CONSTITUENCY",    latitude=-22.5550, longitude=17.0444, population=85000),
            dict(name="Windhoek Central Hospital", code="NA-WCH", location_type="HEALTH_FACILITY", latitude=-22.5609, longitude=17.0658, population=0),
            dict(name="Mulago Hospital",code="UG-MLG",  location_type="HEALTH_FACILITY", latitude=0.3367,  longitude=32.5749, population=0),
        ]
        self.locations = []
        for spec in locs_spec:
            loc, _ = Location.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "location_type": spec["location_type"],
                    "latitude": Decimal(str(spec["latitude"])),
                    "longitude": Decimal(str(spec["longitude"])),
                    "population": spec.get("population", 0),
                },
            )
            self.locations.append(loc)
        self.stdout.write(f"    Locations: {len(self.locations)}")

        # ── System Configurations ──────────────────────────────────────────────
        configs = [
            ("ALERT_THRESHOLD_CRITICAL", "0.9",  "general"),
            ("ALERT_THRESHOLD_HIGH",     "0.8",  "general"),
            ("ALERT_THRESHOLD_MEDIUM",   "0.6",  "general"),
            ("ENABLE_ML_PREDICTIONS",    True,   "features"),
            ("ENABLE_REAL_TIME_ALERTS",  True,   "features"),
            ("DATA_RETENTION_DAYS",      365,    "general"),
            ("MAX_NOTIFICATION_RETRIES", 3,      "general"),
            ("TIME_ZONE",                "Africa/Windhoek", "general"),
        ]
        for key, val, cat in configs:
            SystemConfiguration.objects.get_or_create(
                key=key,
                defaults={
                    "value": val,
                    "category": cat,
                    "is_active": True,
                    "description": f"{key} configuration",
                },
            )
        self.stdout.write(f"    Configurations: {len(configs)}")

        # ── Notifications ─────────────────────────────────────────────────────
        notif_data = [
            ("Critical Alert: Cholera Outbreak Detected", "HIGH",   "ALERT"),
            ("Risk Score Updated: Windhoek +12 points",    "HIGH",   "SYSTEM"),
            ("Response Activated: Level 3 — Windhoek",    "HIGH",   "ALERT"),
            ("New Case Cluster Identified: Oshana Region","NORMAL", "INFO"),
            ("Weekly Surveillance Report Ready",          "NORMAL", "INFO"),
            ("Resource Low Stock: PPE — Windhoek Central Hospital","HIGH","WARNING"),
            ("Escalation Trigger Fired: Level 2→3",      "HIGH",   "ALERT"),
            ("DHIS2 Sync Completed — 1,240 records",     "NORMAL", "INFO"),
        ]
        for title, priority, notif_type in notif_data:
            Notification.objects.get_or_create(
                title=title,
                user=self.admin_user,
                defaults={
                    "message": f"Automated system notification: {title}",
                    "notification_type": notif_type,
                    "priority": priority,
                    "is_read": random.choice([True, False]),
                },
            )
        # Notifications for all users
        extra_notifs = [
            ("Surveillance report ready for review",    "NORMAL", "INFO"),
            ("Your assigned task is due tomorrow",      "HIGH",   "WARNING"),
            ("New case cluster detected in your area",  "HIGH",   "ALERT"),
            ("Meeting scheduled: Coordination call",    "NORMAL", "INFO"),
            ("PPE stock below minimum threshold",       "HIGH",   "WARNING"),
            ("Action item completed by field officer",  "NORMAL", "INFO"),
        ]
        for user in self.users[1:]:
            for title, priority, notif_type in extra_notifs:
                Notification.objects.get_or_create(
                    title=title,
                    user=user,
                    defaults={
                        "message": f"Notification for {user.get_full_name()}: {title}",
                        "notification_type": notif_type,
                        "priority": priority,
                        "is_read": random.choice([True, False, False]),
                    },
                )
        total_notifs = len(notif_data) + len(extra_notifs) * len(self.users[1:])
        self.stdout.write(f"    Notifications: {total_notifs}")

    # =========================================================================
    # 2. SURVEILLANCE
    # =========================================================================

    def _seed_surveillance(self):
        from core.models import Location
        from surveillance.models import (
            DataSource, DiseaseProfile, HealthData,
            AnomalyDetection, CaseCluster, Hotspot, SurveillanceReport,
        )

        locs = list(Location.objects.filter(is_deleted=False))
        if not locs:
            self._seed_core()
            locs = list(Location.objects.filter(is_deleted=False))

        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()

        # ── Disease Profiles ──────────────────────────────────────────────────
        diseases_data = [
            dict(code="A00",   name="Cholera",            category="Bacterial"),
            dict(code="B50",   name="Malaria",            category="Parasitic"),
            dict(code="U07.1", name="COVID-19",           category="Viral"),
            dict(code="A98.4", name="Ebola Virus Disease",category="Viral"),
            dict(code="A15",   name="Tuberculosis",       category="Bacterial"),
            dict(code="A90",   name="Dengue Fever",       category="Viral"),
            dict(code="B04",   name="Mpox",               category="Viral"),
            dict(code="A01",   name="Typhoid Fever",      category="Bacterial"),
        ]
        self.disease_profiles = []
        for d in diseases_data:
            dp, _ = DiseaseProfile.objects.get_or_create(
                disease_code=d["code"],
                defaults={
                    "disease_name": d["name"],
                    "category": d["category"],
                    "is_notifiable": True,
                    "alert_threshold": random.randint(5, 20),
                    "epidemic_threshold": random.randint(20, 100),
                    "incubation_period_min": random.randint(1, 5),
                    "incubation_period_max": random.randint(7, 21),
                    "is_active": True,
                    "symptoms": ["fever", "diarrhoea", "vomiting"],
                    "transmission_routes": ["waterborne", "contact"],
                },
            )
            self.disease_profiles.append(dp)
        self.stdout.write(f"    Disease Profiles: {len(self.disease_profiles)}")

        # ── Data Sources ──────────────────────────────────────────────────────
        source_specs = [
            dict(name="Windhoek Central Hospital EMR",   source_type="HOSPITAL",   loc_code="NA-WCH"),
            dict(name="Khomas Region DHIS2 Node",        source_type="DHIS2",      loc_code="NA-KHO"),
            dict(name="Erongo Regional Lab LIS",           source_type="LABORATORY", loc_code="NA-ERO"),
            dict(name="Mulago Hospital Uganda",           source_type="HOSPITAL",   loc_code="UG-MLG"),
            dict(name="Kampala DHIS2 Node",               source_type="DHIS2",      loc_code="UG-KLA"),
            dict(name="Dar es Salaam Community Clinics",  source_type="CLINIC",     loc_code="TZ-DAR"),
            dict(name="WHO EIOS Feed",                    source_type="API",        loc_code="NA"),
            dict(name="Africa CDC Sentinel Network",      source_type="API",        loc_code="ET"),
        ]
        self.data_sources = []
        for spec in source_specs:
            loc = Location.objects.filter(code=spec["loc_code"]).first() or locs[0]
            ds, _ = DataSource.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "source_type": spec["source_type"],
                    "location": loc,
                    "is_active": True,
                    "last_sync": days_ago(random.randint(0, 3)),
                    "sync_frequency": random.choice([3600, 7200, 86400]),
                    "contact_person": "System Administrator",
                    "contact_email": "admin@oryxshield.gov.na",
                },
            )
            self.data_sources.append(ds)
        self.stdout.write(f"    Data Sources: {len(self.data_sources)}")

        # ── Health Data ───────────────────────────────────────────────────────
        data_types = ["CASE", "LAB_RESULT", "ADMISSION", "SYMPTOM", "DEATH"]
        severities  = ["MILD", "MODERATE", "SEVERE", "CRITICAL"]
        outcomes    = ["RECOVERED", "HOSPITALISED", "UNKNOWN", "DECEASED"]
        genders     = ["M", "F", "U"]
        hd_count = 0
        for _ in range(60):
            ds = random.choice(self.data_sources)
            loc = random.choice(locs)
            dp = random.choice(self.disease_profiles)
            HealthData.objects.create(
                data_source=ds,
                location=loc,
                disease_code=dp.disease_code,
                disease_name=dp.disease_name,
                data_type=random.choice(data_types),
                date_recorded=timezone.now() - timedelta(days=random.randint(0, 90)),
                age=random.randint(1, 85),
                gender=random.choice(genders),
                severity=random.choice(severities),
                outcome=random.choice(outcomes),
                symptoms=["fever", "cough", "diarrhoea"][:random.randint(1, 3)],
                test_type=random.choice(["PCR", "RDT", "Culture"]),
                test_result=random.choice(["POSITIVE", "NEGATIVE", "PENDING"]),
                processed=True,
            )
            hd_count += 1
        self.stdout.write(f"    Health Data records: {hd_count}")

        # ── Anomaly Detections ────────────────────────────────────────────────
        anomaly_types  = ["SPIKE", "TREND", "CLUSTER", "OUTBREAK", "PATTERN"]
        self.anomalies = []
        for i in range(20):
            loc = random.choice(locs)
            dp = random.choice(self.disease_profiles)
            now = timezone.now()
            anm = AnomalyDetection.objects.create(
                location=loc,
                disease_code=dp.disease_code,
                disease_name=dp.disease_name,
                anomaly_type=random.choice(anomaly_types),
                severity=random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
                detection_method=random.choice(["CUSUM", "ZSCORE", "ARIMA", "ML"]),
                confidence_score=Decimal(str(rand_decimal(60.0, 99.0))),
                expected_cases=random.randint(10, 100),
                actual_cases=random.randint(15, 200),
                baseline_cases=random.randint(5, 80),
                percentage_increase=Decimal(str(rand_decimal(10.0, 300.0))),
                start_date=now - timedelta(days=random.randint(3, 14)),
                end_date=now,
                notes=f"Anomalous {dp.disease_name} activity detected in {loc.name}",
            )
            self.anomalies.append(anm)
        self.stdout.write(f"    Anomalies: {len(self.anomalies)}")

        # ── Case Clusters ─────────────────────────────────────────────────────
        self.clusters = []
        for i in range(10):
            loc = random.choice(locs)
            dp = random.choice(self.disease_profiles)
            start = timezone.now() - timedelta(days=random.randint(5, 60))
            cl = CaseCluster.objects.create(
                name=f"{dp.disease_name} Cluster — {loc.name} #{i+1}",
                location=loc,
                disease_code=dp.disease_code,
                disease_name=dp.disease_name,
                case_count=random.randint(5, 80),
                start_date=start,
                end_date=start + timedelta(days=random.randint(5, 30)) if random.random() > 0.4 else None,
                radius_km=Decimal(str(rand_decimal(0.5, 25.0))),
                center_latitude=Decimal(str(float(loc.latitude or 0) + rand_decimal(-0.05, 0.05))),
                center_longitude=Decimal(str(float(loc.longitude or 0) + rand_decimal(-0.05, 0.05))),
                attack_rate=Decimal(str(rand_decimal(1.0, 30.0))),
                population_at_risk=random.randint(5000, 500000),
                detection_method=random.choice(["SaTScan", "Kulldorff", "DBSCAN"]),
                detection_algorithm="SaTScan",
                is_active=random.choice([True, True, False]),
            )
            self.clusters.append(cl)
        self.stdout.write(f"    Case Clusters: {len(self.clusters)}")

        # ── Hotspots ──────────────────────────────────────────────────────────
        self.hotspots = []
        risk_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        for _ in range(15):
            loc = random.choice(locs)
            dp = random.choice(self.disease_profiles)
            cluster = random.choice(self.clusters) if self.clusters else None
            hs = Hotspot.objects.create(
                location=loc,
                disease_code=dp.disease_code,
                disease_name=dp.disease_name,
                risk_level=random.choice(risk_levels),
                case_count=random.randint(3, 200),
                incidence_rate=Decimal(str(rand_decimal(0.5, 80.0))),
                gi_statistic=Decimal(str(rand_decimal(1.5, 12.0))),
                z_score=Decimal(str(rand_decimal(1.5, 6.0))),
                p_value=Decimal(str(rand_decimal(0.001, 0.05))),
                latitude=Decimal(str(float(loc.latitude or 0) + rand_decimal(-0.1, 0.1))),
                longitude=Decimal(str(float(loc.longitude or 0) + rand_decimal(-0.1, 0.1))),
                radius_km=Decimal(str(rand_decimal(1.0, 30.0))),
                start_date=days_ago(random.randint(1, 60)),
                is_active=random.choice([True, True, False]),
                related_cluster=cluster,
            )
            self.hotspots.append(hs)
        self.stdout.write(f"    Hotspots: {len(self.hotspots)}")

        # ── Surveillance Reports ──────────────────────────────────────────────
        report_types = ["DAILY", "WEEKLY", "MONTHLY"]
        for i, rtype in enumerate(report_types):
            loc = locs[i % len(locs)]
            SurveillanceReport.objects.get_or_create(
                title=f"{rtype.capitalize()} Surveillance Report — Week {date.today().isocalendar()[1]}",
                defaults={
                    "report_type": rtype,
                    "location": loc,
                    "start_date": date.today() - timedelta(days=7 * (i + 1)),
                    "end_date": date.today() - timedelta(days=7 * i),
                    "total_cases": random.randint(100, 5000),
                    "new_cases": random.randint(10, 500),
                    "active_clusters": random.randint(0, 10),
                    "active_hotspots": random.randint(0, 8),
                    "anomalies_detected": random.randint(0, 5),
                    "summary": f"Automated {rtype.lower()} surveillance summary for the OryxShield.",
                    "key_findings": ["Cases rising in urban areas", "Lab confirmation rate 78%"],
                    "recommendations": ["Increase surveillance", "Deploy RRT"],
                    "generated_by": admin,
                    "is_published": True,
                    "published_at": days_ago(i),
                },
            )
        self.stdout.write(f"    Surveillance Reports: 3")

    # =========================================================================
    # 3. RISK
    # =========================================================================

    def _seed_risk(self):
        from core.models import Location
        from risk_assessment.models import Alert, RiskScore, Threshold, ThreatClassification

        locs = list(Location.objects.filter(is_deleted=False))
        if not locs:
            self._seed_core()
            locs = list(Location.objects.filter(is_deleted=False))

        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()

        diseases = [
            ("A00", "Cholera"), ("B50", "Malaria"), ("U07.1", "COVID-19"),
            ("A98.4", "Ebola"), ("A15", "Tuberculosis"), ("A90", "Dengue"),
        ]

        def score_to_level(s):
            if s >= 9.0:   return "CRITICAL"
            if s >= 7.5:   return "VERY_HIGH"
            if s >= 6.0:   return "HIGH"
            if s >= 4.0:   return "MEDIUM"
            if s >= 2.0:   return "LOW"
            return "VERY_LOW"

        # ── Risk Scores ───────────────────────────────────────────────────────
        self.risk_scores = []
        used_combos = set()
        attempts = 0
        while len(self.risk_scores) < 40 and attempts < 200:
            attempts += 1
            loc = random.choice(locs)
            dc, dn = random.choice(diseases)
            assess_date = date.today() - timedelta(days=random.randint(0, 30))
            combo = (str(loc.id), dc, assess_date.isoformat())
            if combo in used_combos:
                continue
            used_combos.add(combo)
            overall = rand_decimal(0, 10)
            try:
                rs = RiskScore.objects.create(
                    location=loc,
                    disease_code=dc,
                    disease_name=dn,
                    overall_score=Decimal(str(overall)),
                    risk_level=score_to_level(overall),
                    incidence_score=Decimal(str(rand_decimal(0, 10))),
                    transmission_score=Decimal(str(rand_decimal(0, 10))),
                    severity_score=Decimal(str(rand_decimal(0, 10))),
                    vulnerability_score=Decimal(str(rand_decimal(0, 10))),
                    capacity_score=Decimal(str(rand_decimal(0, 10))),
                    r_naught=Decimal(str(rand_decimal(0.8, 5.0))),
                    case_fatality_rate=Decimal(str(rand_decimal(0.1, 10.0))),
                    attack_rate=Decimal(str(rand_decimal(0.5, 30.0))),
                    doubling_time=Decimal(str(rand_decimal(2.0, 30.0))),
                    population_at_risk=random.randint(50000, 5000000),
                    vulnerable_population=random.randint(5000, 500000),
                    assessment_date=assess_date,
                    is_active=True,
                    confidence_level=Decimal(str(rand_decimal(60, 99))),
                )
                self.risk_scores.append(rs)
            except Exception:
                pass
        self.stdout.write(f"    Risk Scores: {len(self.risk_scores)}")

        # ── Thresholds ────────────────────────────────────────────────────────
        # Actual fields: warning_value, alert_value, critical_value (three tiers)
        threshold_specs = [
            dict(name="Case Count Threshold",    threshold_type="CASE_COUNT",    warn=20,  alert=50,  crit=200),
            dict(name="Incidence Rate Threshold", threshold_type="INCIDENCE_RATE",warn=50,  alert=100, crit=500),
            dict(name="Mortality Rate Threshold", threshold_type="MORTALITY_RATE",warn=1.0, alert=3.0, crit=5.0),
            dict(name="R0 Epidemic Threshold",    threshold_type="R_NAUGHT",      warn=1.0, alert=1.5, crit=2.5),
            dict(name="Risk Score Threshold",     threshold_type="RISK_SCORE",    warn=4.0, alert=7.0, crit=9.0),
        ]
        self.thresholds = []
        for spec in threshold_specs:
            try:
                th, _ = Threshold.objects.get_or_create(
                    name=spec["name"],
                    defaults={
                        "threshold_type": spec["threshold_type"],
                        "warning_value": Decimal(str(spec["warn"])),
                        "alert_value": Decimal(str(spec["alert"])),
                        "critical_value": Decimal(str(spec["crit"])),
                        "is_active": True,
                        "description": f"Automated threshold: {spec['name']}",
                    },
                )
                self.thresholds.append(th)
            except Exception as e:
                self.stdout.write(f"    Threshold skip: {e}")
        self.stdout.write(f"    Thresholds: {len(self.thresholds)}")

        # ── Alerts ────────────────────────────────────────────────────────────
        alert_specs = [
            dict(title="CRITICAL: Ebola Suspected Case — Kampala",   severity="CRITICAL", status="ACTIVE"),
            dict(title="HIGH: Cholera Outbreak — Erongo Region",    severity="ALERT",    status="ACTIVE"),
            dict(title="HIGH: COVID-19 Spike — Windhoek CBD",         severity="ALERT",    status="ACKNOWLEDGED"),
            dict(title="MEDIUM: Malaria Cluster — Oshikoto Region",    severity="WARNING",  status="INVESTIGATING"),
            dict(title="MEDIUM: Dengue Alert — Dar es Salaam",       severity="WARNING",  status="ACTIVE"),
            dict(title="HIGH: TB Cases Rising — Addis Ababa",        severity="ALERT",    status="ACTIVE"),
            dict(title="CRITICAL: Mpox Outbreak — Kampala",          severity="CRITICAL", status="ACTIVE"),
            dict(title="LOW: Typhoid Cases — Hardap Region",         severity="INFO",     status="RESOLVED"),
            dict(title="HIGH: Cholera Waterborne — Lake Victoria",   severity="ALERT",    status="ACTIVE"),
            dict(title="MEDIUM: Malaria High Season — Uganda",       severity="WARNING",  status="ACTIVE"),
        ]
        self.alerts = []
        for i, spec in enumerate(alert_specs):
            loc = locs[i % len(locs)]
            dc, dn = diseases[i % len(diseases)]
            rs = self.risk_scores[i % len(self.risk_scores)] if self.risk_scores else None
            alert, _ = Alert.objects.get_or_create(
                title=spec["title"],
                defaults={
                    "description": f"Automated alert: {spec['title']}. Immediate attention required.",
                    "severity": spec["severity"],
                    "status": spec["status"],
                    "alert_type": "OUTBREAK",
                    "location": loc,
                    "disease_code": dc,
                    "disease_name": dn,
                    "related_risk_score": rs,
                    "acknowledged_by": admin if spec["status"] == "ACKNOWLEDGED" else None,
                    "acknowledged_at": days_ago(1) if spec["status"] == "ACKNOWLEDGED" else None,
                },
            )
            self.alerts.append(alert)
        self.stdout.write(f"    Alerts: {len(self.alerts)}")

        # ── Threat Classifications ─────────────────────────────────────────────
        tc_count = 0
        for dc, dn in diseases[:5]:
            loc = random.choice(locs)
            rs = random.choice(self.risk_scores) if self.risk_scores else None
            try:
                ThreatClassification.objects.get_or_create(
                    disease_code=dc,
                    location=loc,
                    assessment_date=date.today(),
                    defaults={
                        "disease_name": dn,
                        "threat_level": random.choice(["LOW", "MODERATE", "HIGH", "SEVERE"]),
                        "threat_score": Decimal(str(rand_decimal(3.0, 9.5))),
                        "pandemic_potential": random.choice([True, False]),
                        "cross_border_risk": random.choice([True, False]),
                        "economic_impact_level": random.choice(["LOW", "MEDIUM", "HIGH"]),
                        "justification": f"Threat classification for {dn} based on current surveillance data.",
                        "key_factors": ["High case count", "Cross-border movement", "Limited healthcare capacity"],
                        "assessed_by": admin,
                        "related_risk_score": rs,
                    },
                )
                tc_count += 1
            except Exception:
                pass
        self.stdout.write(f"    Threat Classifications: {tc_count}")

        # ── Risk Factors ──────────────────────────────────────────────────────
        try:
            from risk_assessment.models import RiskFactor
            from core.models import Location as Loc
            locs_for_rf = list(Loc.objects.filter(is_deleted=False))
            rf_specs = [
                dict(name="Urban Overcrowding",         category="DEMOGRAPHIC",    weight=0.8,  disease_codes=["A00", "B50"]),
                dict(name="Poor Water & Sanitation",    category="ENVIRONMENTAL",  weight=0.9,  disease_codes=["A00", "A01"]),
                dict(name="Low Vaccination Coverage",   category="BEHAVIORAL",     weight=0.85, disease_codes=["U07.1"]),
                dict(name="Weak Healthcare Capacity",   category="HEALTHCARE",     weight=0.9,  disease_codes=[]),
                dict(name="Poverty Index",              category="SOCIOECONOMIC",  weight=0.7,  disease_codes=[]),
                dict(name="Cross-Border Movement",      category="GEOGRAPHIC",     weight=0.75, disease_codes=["A98.4", "U07.1"]),
                dict(name="Rainfall Anomaly",           category="ENVIRONMENTAL",  weight=0.6,  disease_codes=["B50", "A90"]),
                dict(name="Malnutrition Rate",          category="DEMOGRAPHIC",    weight=0.8,  disease_codes=["A15"]),
            ]
            rf_count = 0
            for spec in rf_specs:
                loc = random.choice(locs_for_rf) if locs_for_rf else None
                try:
                    RiskFactor.objects.get_or_create(
                        name=spec["name"],
                        defaults={
                            "category": spec["category"],
                            "description": f"Risk factor: {spec['name']}",
                            "weight": Decimal(str(spec["weight"])),
                            "disease_codes": spec["disease_codes"],
                            "location": loc,
                            "is_active": True,
                            "data_source": "WHO Global Health Observatory",
                        },
                    )
                    rf_count += 1
                except Exception as e:
                    self.stdout.write(f"    RiskFactor skip: {e}")
            self.stdout.write(f"    Risk Factors: {rf_count}")
        except Exception as e:
            self.stdout.write(f"    RiskFactor section error: {e}")

        # ── Predictive Models ─────────────────────────────────────────────────
        try:
            from risk_assessment.models import PredictiveModel
            pm_specs = [
                dict(name="Cholera Outbreak Predictor v2",  model_type="TIME_SERIES",    algo="LSTM",             version="2.1.0", acc=88.5),
                dict(name="Malaria Seasonality Model",      model_type="REGRESSION",     algo="XGBoost",          version="1.4.2", acc=82.3),
                dict(name="COVID-19 Spread Ensemble",       model_type="ENSEMBLE",       algo="Random Forest+LSTM",version="3.0.0",acc=91.2),
                dict(name="Ebola Risk Classifier",          model_type="CLASSIFICATION", algo="SVM",              version="1.0.1", acc=79.8),
                dict(name="General Outbreak Forecaster",    model_type="TIME_SERIES",    algo="ARIMA",            version="2.0.0", acc=75.1),
            ]
            pm_count = 0
            for spec in pm_specs:
                try:
                    PredictiveModel.objects.get_or_create(
                        name=spec["name"],
                        defaults={
                            "model_type": spec["model_type"],
                            "description": f"ML model: {spec['name']}",
                            "algorithm": spec["algo"],
                            "version": spec["version"],
                            "accuracy": Decimal(str(spec["acc"])),
                            "precision": Decimal(str(rand_decimal(70.0, 95.0))),
                            "recall": Decimal(str(rand_decimal(70.0, 95.0))),
                            "f1_score": Decimal(str(rand_decimal(70.0, 95.0))),
                            "training_data_size": random.randint(5000, 500000),
                            "trained_at": days_ago(random.randint(7, 180)),
                            "is_active": True,
                            "is_deployed": random.choice([True, False]),
                            "prediction_count": random.randint(0, 5000),
                            "last_used": days_ago(random.randint(0, 14)) if random.random() > 0.3 else None,
                        },
                    )
                    pm_count += 1
                except Exception as e:
                    self.stdout.write(f"    PredictiveModel skip: {e}")
            self.stdout.write(f"    Predictive Models: {pm_count}")
        except Exception as e:
            self.stdout.write(f"    PredictiveModel section error: {e}")

    # =========================================================================
    # 4. RESPONSE
    # =========================================================================

    def _seed_response(self):
        from core.models import Location
        from response.models import (
            ResponseLevel, ResponseProtocol, ResponseActivation,
            ActionItem, DecisionLog,
        )

        locs = list(Location.objects.filter(is_deleted=False))
        if not locs:
            self._seed_core()
            locs = list(Location.objects.filter(is_deleted=False))

        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()
        users = list(User.objects.all())

        # ── Response Levels ───────────────────────────────────────────────────
        levels_spec = [
            dict(level=1, name="Routine Surveillance",  threshold=0.0,  desc="Standard surveillance and monitoring."),
            dict(level=2, name="Enhanced Surveillance", threshold=4.0,  desc="Increased data collection and lab readiness."),
            dict(level=3, name="Targeted Response",     threshold=6.0,  desc="Rapid response team deployment and contact tracing."),
            dict(level=4, name="Coordinated Response",  threshold=7.5,  desc="Multi-agency coordination and resource mobilisation."),
            dict(level=5, name="Emergency Response",    threshold=9.0,  desc="Full emergency operations and national mobilisation."),
        ]
        self.response_levels = []
        for spec in levels_spec:
            rl, _ = ResponseLevel.objects.get_or_create(
                level=spec["level"],
                defaults={
                    "name": spec["name"],
                    "description": spec["desc"],
                    "risk_score_threshold": Decimal(str(spec["threshold"])),
                    "required_actions": ["Surveillance", "Reporting", "Communication"],
                    "is_active": True,
                },
            )
            self.response_levels.append(rl)
        self.stdout.write(f"    Response Levels: {len(self.response_levels)}")

        # ── Response Protocols ────────────────────────────────────────────────
        proto_specs = [
            dict(name="Cholera Outbreak Protocol",    code="PROTO-CHO-01", disease_codes=["A00"]),
            dict(name="Ebola Response Protocol",      code="PROTO-EBO-01", disease_codes=["A98.4"]),
            dict(name="COVID-19 Surge Protocol",      code="PROTO-COV-01", disease_codes=["U07.1"]),
            dict(name="Malaria High Season Protocol", code="PROTO-MAL-01", disease_codes=["B50"]),
            dict(name="General Outbreak Response",    code="PROTO-GEN-01", disease_codes=[]),
        ]
        self.protocols = []
        for spec in proto_specs:
            proto, _ = ResponseProtocol.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "protocol_type": "DISEASE" if spec["disease_codes"] else "GENERAL",
                    "disease_codes": spec["disease_codes"],
                    "description": f"Standard operating procedure: {spec['name']}",
                    "objectives": ["Contain outbreak", "Protect population", "Restore normalcy"],
                    "procedures": [
                        {"title": "Deploy Rapid Response Team", "description": "Mobilise RRT to affected area within 2 hours.", "responsible_team": "Operations"},
                        {"title": "Activate EOC", "description": "Open the Emergency Operations Centre and brief leadership.", "responsible_team": "Coordination"},
                        {"title": "Issue Public Communication", "description": "Draft and release first public health advisory.", "responsible_team": "Communications"},
                        {"title": "Establish Case Surveillance", "description": "Set up active case finding and line listing.", "responsible_team": "Surveillance"},
                        {"title": "Coordinate Lab Testing", "description": "Ship samples to reference lab and track results.", "responsible_team": "Surveillance"},
                        {"title": "Procure Critical Supplies", "description": "Emergency purchase order for PPE, test kits, and medications.", "responsible_team": "Logistics"},
                        {"title": "Community Engagement", "description": "Brief community leaders and engage risk communication channels.", "responsible_team": "Communications"},
                    ],
                    "is_active": True,
                    "created_by": admin,
                },
            )
            self.protocols.append(proto)
        self.stdout.write(f"    Response Protocols: {len(self.protocols)}")

        # ── Response Activations ──────────────────────────────────────────────
        statuses = ["ACTIVE", "ACTIVE", "ACTIVE", "ESCALATED", "COMPLETED"]
        self.activations = []
        for i in range(6):
            proto = self.protocols[i % len(self.protocols)]
            rl = self.response_levels[min(i + 1, 4)]
            loc = locs[i % len(locs)]
            code = f"ACT-{date.today().strftime('%Y%m%d')}-{str(i+1).zfill(3)}"
            act, _ = ResponseActivation.objects.get_or_create(
                activation_code=code,
                defaults={
                    "protocol": proto,
                    "response_level": rl,
                    "location": loc,
                    "status": statuses[i % len(statuses)],
                    "disease_code": proto.disease_codes[0] if proto.disease_codes else "A00",
                    "disease_name": proto.name.replace(" Protocol", "").replace(" Response", ""),
                    "activated_by": admin,
                    "incident_commander": admin,
                    "justification": f"Risk score exceeded threshold. Automated activation of {proto.name}.",
                    "objectives": ["Contain outbreak", "Prevent spread", "Minimise casualties"],
                    "personnel_deployed": random.randint(5, 50),
                    "completion_percentage": 100 if statuses[i % len(statuses)] == "COMPLETED" else random.randint(10, 80),
                },
            )
            self.activations.append(act)
        self.stdout.write(f"    Response Activations: {len(self.activations)}")

        # ── Action Items ──────────────────────────────────────────────────────
        action_specs = [
            ("Deploy Rapid Response Team to affected area", "HIGH",     "PENDING"),
            ("Activate Emergency Operations Centre",        "CRITICAL", "IN_PROGRESS"),
            ("Establish isolation facilities",              "HIGH",     "COMPLETED"),
            ("Conduct contact tracing — 200 contacts",     "HIGH",     "IN_PROGRESS"),
            ("Distribute PPE to frontline workers",        "MEDIUM",   "PENDING"),
            ("Issue public health advisory",               "HIGH",     "COMPLETED"),
            ("Coordinate laboratory testing capacity",     "HIGH",     "IN_PROGRESS"),
            ("Brief Ministry of Health officials",         "CRITICAL", "COMPLETED"),
        ]
        for i, (title, priority, status_val) in enumerate(action_specs):
            act = self.activations[i % len(self.activations)]
            assignee = users[i % len(users)]
            ActionItem.objects.get_or_create(
                title=title,
                response_activation=act,
                defaults={
                    "description": f"Action required: {title}",
                    "priority": priority,
                    "status": status_val,
                    "assigned_to": assignee,
                    "due_date": timezone.now() + timedelta(days=random.randint(1, 14)),
                    "completion_notes": "Completed as per SOP." if status_val == "COMPLETED" else "",
                    "completed_at": days_ago(random.randint(0, 3)) if status_val == "COMPLETED" else None,
                },
            )
        self.stdout.write(f"    Action Items: {len(action_specs)}")

        # ── Decision Logs ─────────────────────────────────────────────────────
        decisions = [
            ("Escalation Decision",     "Escalate from Level 2 to Level 3",         "Escalate response due to increasing case counts."),
            ("Resource Authorisation",  "Emergency procurement of 10,000 RDTs",     "Authorise emergency procurement of rapid diagnostic tests."),
            ("Field Deployment",        "Deploy teams to border crossing points",    "Deploy field teams to border crossings."),
            ("Quarantine Order",        "Mandatory quarantine for exposed persons",  "Issue mandatory quarantine order for exposed individuals."),
        ]
        for i, (title, made, rationale) in enumerate(decisions):
            act = self.activations[i % len(self.activations)]
            DecisionLog.objects.get_or_create(
                decision_title=title,
                response_activation=act,
                defaults={
                    "decision_description": made,
                    "situation": "Outbreak situation requiring immediate decision.",
                    "options_considered": ["Option A: Escalate", "Option B: Monitor", "Option C: Contain"],
                    "decision_made": made,
                    "rationale": rationale,
                    "decided_by": admin,
                    "expected_outcome": "Reduction in case count within 14 days.",
                },
            )
        self.stdout.write(f"    Decision Logs: {len(decisions)}")

    # =========================================================================
    # 5. COORDINATION
    # =========================================================================

    def _seed_coordination(self):
        try:
            from coordination.models import Agency, CoordinationTeam, Task, Meeting, TeamMembership
        except ImportError:
            self.stdout.write(self.style.WARNING("    coordination models not importable — skipped."))
            return

        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()
        users = list(User.objects.all())

        # ── Agencies ──────────────────────────────────────────────────────────
        # Agency has no `code` field; required: name, acronym, agency_type,
        # primary_contact, contact_email, contact_phone
        agencies_spec = [
            dict(name="Ministry of Health and Social Services Namibia",  acronym="MOHSS-NA",   agency_type="GOVERNMENT"),
            dict(name="WHO Africa Regional Office",acronym="WHO-AFRO",  agency_type="INTERNATIONAL"),
            dict(name="Namibia Red Cross Society",   acronym="NRCS",      agency_type="NGO"),
            dict(name="Africa CDC",                acronym="ACDC",      agency_type="INTERNATIONAL"),
            dict(name="UNICEF Namibia",              acronym="UNICEF-NA", agency_type="INTERNATIONAL"),
            dict(name="Medecins Sans Frontieres",  acronym="MSF-KE",    agency_type="NGO"),
        ]
        self.agencies = []
        for spec in agencies_spec:
            try:
                agency, _ = Agency.objects.get_or_create(
                    name=spec["name"],
                    defaults={
                        "acronym": spec["acronym"],
                        "agency_type": spec["agency_type"],
                        "primary_contact": f"Director, {spec['name']}",
                        "contact_email": f"contact@{spec['acronym'].lower().replace('-','')}.org",
                        "contact_phone": "+264810000000",
                        "is_active": True,
                        "description": f"{spec['name']} — coordination partner",
                    },
                )
                self.agencies.append(agency)
            except Exception as e:
                self.stdout.write(f"    Agency skip: {e}")
        self.stdout.write(f"    Agencies: {len(self.agencies)}")

        if not self.agencies:
            return

        # ── CoordinationTeams ─────────────────────────────────────────────────
        # CoordinationTeam required: name, code (unique), team_type, mandate
        # FK: lead_agency, team_leader
        teams_spec = [
            dict(name="Rapid Response Team Alpha",    code="RRT-A",  team_type="INCIDENT"),
            dict(name="Epidemiology Task Force",      code="EPI-TF", team_type="TASK_FORCE"),
            dict(name="Laboratory Working Group",     code="LAB-WG", team_type="WORKING_GROUP"),
            dict(name="Logistics Technical Group",    code="LOG-TG", team_type="TECHNICAL"),
            dict(name="Emergency Operations Centre",  code="EOC-01", team_type="EOC"),
        ]
        self.teams = []
        for spec in teams_spec:
            lead = random.choice(self.agencies)
            try:
                team, _ = CoordinationTeam.objects.get_or_create(
                    code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "team_type": spec["team_type"],
                        "mandate": f"Coordinate {spec['name']} activities during health emergencies",
                        "lead_agency": lead,
                        "team_leader": admin,
                        "is_active": True,
                        "notes": f"{spec['name']} — operational coordination team",
                    },
                )
                self.teams.append(team)
                # Memberships link agencies, not users
                for ag in self.agencies[:3]:
                    try:
                        TeamMembership.objects.get_or_create(
                            team=team, agency=ag,
                            defaults={
                                "role": "MEMBER",
                                "is_active": True,
                                "primary_representative": admin,
                            },
                        )
                    except Exception:
                        pass
            except Exception as e:
                self.stdout.write(f"    Team skip: {e}")
        self.stdout.write(f"    Teams: {len(self.teams)}")

        # ── Tasks ─────────────────────────────────────────────────────────────
        # Task FK: coordination_team, assigned_to_user, assigned_by
        task_specs = [
            ("Contact tracing — Windhoek CBD cluster",       "HIGH",     "IN_PROGRESS"),
            ("Epidemiological investigation report",        "HIGH",     "ASSIGNED"),
            ("Laboratory sample collection and transport",  "CRITICAL", "IN_PROGRESS"),
            ("Public health messaging — radio campaign",    "MEDIUM",   "COMPLETED"),
            ("Field supervision — isolation centres",       "HIGH",     "IN_PROGRESS"),
            ("Data entry and DHIS2 synchronisation",        "MEDIUM",   "ASSIGNED"),
        ]
        task_count = 0
        for i, (title, priority, status_val) in enumerate(task_specs):
            if not self.teams:
                break
            cteam = self.teams[i % len(self.teams)]
            agency = self.agencies[i % len(self.agencies)]
            assignee = users[i % len(users)]
            try:
                Task.objects.get_or_create(
                    title=title,
                    defaults={
                        "description": f"Task: {title}",
                        "coordination_team": cteam,
                        "assigned_to_agency": agency,
                        "assigned_to_user": assignee,
                        "assigned_by": admin,
                        "priority": priority,
                        "status": status_val,
                        "due_date": timezone.now() + timedelta(days=random.randint(1, 10)),
                    },
                )
                task_count += 1
            except Exception as e:
                self.stdout.write(f"    Task skip: {e}")
        self.stdout.write(f"    Tasks: {task_count}")

        # ── Meetings ──────────────────────────────────────────────────────────
        # Meeting required: coordination_team, title, scheduled_start, scheduled_end
        # FK: chair; meeting_type choices: REGULAR/EMERGENCY/BRIEFING/WORKING/REVIEW/DEBRIEF
        meeting_specs = [
            ("Emergency Operations Committee",    "COMPLETED", -2),
            ("Daily Situation Report Briefing",   "COMPLETED", -1),
            ("Inter-agency Coordination Meeting", "SCHEDULED",  1),
            ("Technical Working Group — Labs",    "SCHEDULED",  2),
            ("Ministerial Briefing",              "SCHEDULED",  5),
        ]
        meeting_count = 0
        for title, status_val, day_offset in meeting_specs:
            cteam = random.choice(self.teams) if self.teams else None
            if not cteam:
                break
            start = timezone.now() + timedelta(days=day_offset)
            try:
                Meeting.objects.get_or_create(
                    title=title,
                    defaults={
                        "coordination_team": cteam,
                        "status": status_val,
                        "meeting_type": random.choice(["BRIEFING", "WORKING", "REVIEW"]),
                        "scheduled_start": start,
                        "scheduled_end": start + timedelta(hours=2),
                        "venue": random.choice(["EOC Conference Room", "Ministry Boardroom"]),
                        "is_virtual": random.choice([True, False]),
                        "agenda": ["Situation update", "Action items review", "Next steps"],
                        "chair": admin,
                    },
                )
                meeting_count += 1
            except Exception as e:
                self.stdout.write(f"    Meeting skip: {e}")
        self.stdout.write(f"    Meetings: {meeting_count}")

        # ── Team Memberships ──────────────────────────────────────────────────
        try:
            from coordination.models import TeamMembership
            tm_count = 0
            roles = ["LEAD", "MEMBER", "OBSERVER", "COORDINATOR"]
            for team in self.teams:
                for i, agency in enumerate(self.agencies[:3]):
                    try:
                        rep = users[i % len(users)]
                        alt = users[(i + 1) % len(users)]
                        TeamMembership.objects.get_or_create(
                            team=team,
                            agency=agency,
                            defaults={
                                "role": roles[i % len(roles)],
                                "primary_representative": rep,
                                "alternate_representative": alt,
                                "is_active": True,
                            },
                        )
                        tm_count += 1
                    except Exception:
                        pass
            self.stdout.write(f"    Team Memberships: {tm_count}")
        except Exception as e:
            self.stdout.write(f"    TeamMembership section error: {e}")

        # ── Meeting Attendances ───────────────────────────────────────────────
        try:
            from coordination.models import MeetingAttendance
            meetings_qs = list(Meeting.objects.all()[:5])
            ma_count = 0
            for meeting in meetings_qs:
                for user in users[:4]:
                    try:
                        MeetingAttendance.objects.get_or_create(
                            meeting=meeting,
                            attendee=user,
                            defaults={
                                "status": random.choice(["ATTENDED", "ATTENDED", "ABSENT", "INVITED"]),
                            },
                        )
                        ma_count += 1
                    except Exception:
                        pass
            self.stdout.write(f"    Meeting Attendances: {ma_count}")
        except Exception as e:
            self.stdout.write(f"    MeetingAttendance section error: {e}")

    # =========================================================================
    # 6. RESOURCES
    # =========================================================================

    def _seed_resources(self):
        try:
            from resources.models import ResourceCategory, ResourceItem, Facility, Inventory
        except ImportError as e:
            self.stdout.write(self.style.WARNING(f"    resources models not importable — skipped. ({e})"))
            return

        from core.models import Location
        locs = list(Location.objects.filter(is_deleted=False))
        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()

        # ── Categories ────────────────────────────────────────────────────────
        # ResourceCategory requires: name (unique), code (unique), standard_unit
        cat_specs = [
            ("PPE & Protective Equipment", "PPE",      "pieces"),
            ("Pharmaceuticals",            "PHARMA",   "tablets"),
            ("Medical Equipment",          "EQUIP",    "units"),
            ("Laboratory Supplies",        "LAB",      "kits"),
            ("Logistics & Transport",      "LOGISTICS", "units"),
        ]
        self.categories = []
        for name, code, unit in cat_specs:
            try:
                cat, _ = ResourceCategory.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "description": f"{name} category",
                        "standard_unit": unit,
                        "is_active": True,
                    },
                )
                self.categories.append(cat)
            except Exception as e:
                self.stdout.write(f"    Category skip: {e}")
        self.stdout.write(f"    Resource Categories: {len(self.categories)}")

        # ── Facilities ────────────────────────────────────────────────────────
        # Facility requires: code (unique), name, facility_type, location
        fac_specs = [
            dict(name="Windhoek Central Hospital",        code="FAC-WCH",    fac_type="HOSPITAL",  loc_code="NA-WCH", beds=500),
            dict(name="Khomas Regional Referral Hospital",  code="FAC-KHO-REF",fac_type="HOSPITAL",  loc_code="NA-KHO", beds=300),
            dict(name="Erongo Regional Warehouse",          code="FAC-ERO-WH", fac_type="WAREHOUSE", loc_code="NA-ERO", beds=0),
            dict(name="Mulago National Referral Hospital", code="FAC-UG-MLG", fac_type="HOSPITAL",  loc_code="UG-MLG", beds=450),
            dict(name="Dar es Salaam Regional Clinic",     code="FAC-TZ-DAR", fac_type="CLINIC",    loc_code="TZ-DAR", beds=80),
            dict(name="Addis Ababa Emergency Stockpile",   code="FAC-ET-AA",  fac_type="WAREHOUSE", loc_code="ET-AA",  beds=0),
        ]
        self.facilities = []
        for spec in fac_specs:
            loc = Location.objects.filter(code=spec["loc_code"]).first() or locs[0]
            try:
                fac, _ = Facility.objects.get_or_create(
                    code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "facility_type": spec["fac_type"],
                        "location": loc,
                        "total_beds": spec["beds"] or None,
                        "is_operational": True,
                        "contact_email": "facility@oryxshield.gov.na",
                        "contact_phone": "+264810000000",
                    },
                )
                self.facilities.append(fac)
            except Exception as e:
                self.stdout.write(f"    Facility skip: {e}")
        self.stdout.write(f"    Facilities: {len(self.facilities)}")

        # ── Resource Items ────────────────────────────────────────────────────
        # ResourceItem requires: code (unique), name, category, unit_of_measure
        item_specs = [
            dict(name="N95 Respirator Masks",          code="ITEM-PPE-001", unit="box",    cat_code="PPE",    cost=45.0),
            dict(name="Nitrile Examination Gloves",    code="ITEM-PPE-002", unit="box",    cat_code="PPE",    cost=12.0),
            dict(name="Protective Gowns",              code="ITEM-PPE-003", unit="piece",  cat_code="PPE",    cost=8.5),
            dict(name="Oral Rehydration Salts (ORS)",  code="ITEM-PHA-001", unit="sachet", cat_code="PHARMA", cost=0.3),
            dict(name="Ciprofloxacin 500mg",           code="ITEM-PHA-002", unit="tablet", cat_code="PHARMA", cost=0.15),
            dict(name="Artemether-Lumefantrine",        code="ITEM-PHA-003", unit="tablet", cat_code="PHARMA", cost=0.8),
            dict(name="Malaria RDT",                   code="ITEM-LAB-001", unit="test",   cat_code="LAB",    cost=1.5),
            dict(name="COVID-19 PCR Kit",              code="ITEM-LAB-002", unit="kit",    cat_code="LAB",    cost=25.0),
            dict(name="Pulse Oximeter",                code="ITEM-EQP-001", unit="unit",   cat_code="EQUIP",  cost=35.0),
            dict(name="Oxygen Concentrator",           code="ITEM-EQP-002", unit="unit",   cat_code="EQUIP",  cost=800.0),
        ]
        self.resource_items = []
        for spec in item_specs:
            cat = ResourceCategory.objects.filter(code=spec["cat_code"]).first()
            try:
                item, _ = ResourceItem.objects.get_or_create(
                    code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "category": cat,
                        "unit_of_measure": spec["unit"],
                        "unit_cost": Decimal(str(spec["cost"])),
                        "reorder_point": random.randint(50, 500),
                        "minimum_stock_level": random.randint(10, 100),
                        "is_critical": spec["cat_code"] in ("PPE", "PHARMA"),
                        "is_active": True,
                    },
                )
                self.resource_items.append(item)
            except Exception as e:
                self.stdout.write(f"    Item skip: {e}")
        self.stdout.write(f"    Resource Items: {len(self.resource_items)}")

        # ── Inventory ─────────────────────────────────────────────────────────
        # Model is Inventory (not InventoryItem); field is quantity_available not quantity_on_hand
        inv_count = 0
        for fac in self.facilities:
            for item in random.sample(self.resource_items, min(5, len(self.resource_items))):
                qty = random.randint(10, 2000)
                try:
                    Inventory.objects.get_or_create(
                        facility=fac,
                        resource_item=item,
                        defaults={
                            "quantity_available": qty,
                            "quantity_reserved": random.randint(0, int(qty * 0.2)),
                            "batch_number": f"BATCH-{random.randint(1000, 9999)}",
                            "expiry_date": date.today() + timedelta(days=random.randint(30, 730)),
                            "storage_location": random.choice(["Cold Chain", "General Store", "Emergency Bay"]),
                            "status": "AVAILABLE",
                        },
                    )
                    inv_count += 1
                except Exception:
                    pass
        self.stdout.write(f"    Inventory Items: {inv_count}")

        # ── Suppliers ─────────────────────────────────────────────────────────
        try:
            from resources.models import Supplier
            sup_specs = [
                dict(name="Meditech Supplies Ltd",      code="SUP-001"),
                dict(name="PharmaGlobal Southern Africa",   code="SUP-002"),
                dict(name="MedEquip International",     code="SUP-003"),
                dict(name="LabSupply Africa",            code="SUP-004"),
                dict(name="WHO Emergency Supply Hub",   code="SUP-005"),
                dict(name="UNICEF Supply Division",     code="SUP-006"),
            ]
            self.suppliers = []
            for spec in sup_specs:
                try:
                    sup, _ = Supplier.objects.get_or_create(
                        code=spec["code"],
                        defaults={
                            "name": spec["name"],
                            "contact_person": "Procurement Manager",
                            "contact_email": f"orders@supplier{spec['code']}.com",
                            "contact_phone": f"+{random.randint(100000000, 999999999)}",
                            "is_active": True,
                            "is_approved": True,
                            "reliability_rating": Decimal(str(rand_decimal(3.0, 5.0))),
                        },
                    )
                    if self.resource_items:
                        sup.supplies.set(random.sample(self.resource_items, min(3, len(self.resource_items))))
                    self.suppliers.append(sup)
                except Exception as e:
                    self.stdout.write(f"    Supplier skip: {e}")
            self.stdout.write(f"    Suppliers: {len(self.suppliers)}")
        except Exception as e:
            self.stdout.write(f"    Supplier section error: {e}")
            self.suppliers = []

        # ── Stock Movements ───────────────────────────────────────────────────
        try:
            from resources.models import StockMovement
            sm_count = 0
            movement_types = ["RECEIPT", "ISSUE", "TRANSFER", "ADJUSTMENT", "RETURN"]
            inventories = list(Inventory.objects.all()[:20])
            for i in range(40):
                if not inventories or not self.facilities:
                    break
                inv = random.choice(inventories)
                mv_type = random.choice(movement_types)
                try:
                    StockMovement.objects.create(
                        movement_type=mv_type,
                        resource_item=inv.resource_item,
                        quantity=random.randint(1, 500),
                        from_facility=inv.facility if mv_type in ("TRANSFER", "ISSUE") else None,
                        to_facility=random.choice(self.facilities) if mv_type in ("TRANSFER", "RECEIPT") else None,
                        reference_number=f"SM-{2026}-{i+1:05d}-{random.randint(1000,9999)}",
                        notes=f"Stock {mv_type.lower()} for {inv.resource_item.name}",
                        recorded_by=admin,
                    )
                    sm_count += 1
                except Exception as e:
                    if sm_count == 0:
                        self.stdout.write(f"    SM skip sample: {e}")
            self.stdout.write(f"    Stock Movements: {sm_count}")
        except Exception as e:
            self.stdout.write(f"    StockMovement section error: {e}")

        # ── Procurement Requests ──────────────────────────────────────────────
        try:
            from resources.models import ProcurementRequest, ProcurementItem
            pr_count = 0
            pr_statuses = ["DRAFT", "SUBMITTED", "APPROVED", "ORDERED", "COMPLETED"]
            for i in range(8):
                fac = self.facilities[i % len(self.facilities)]
                sup = self.suppliers[i % len(self.suppliers)] if self.suppliers else None
                status = pr_statuses[i % len(pr_statuses)]
                try:
                    pr = ProcurementRequest.objects.create(
                        request_number=f"PR-{2026}-{i+1:04d}",
                        requesting_facility=fac,
                        status=status,
                        requested_by=admin,
                        priority=random.choice(["LOW", "MEDIUM", "HIGH", "URGENT"]),
                        required_by_date=date.today() + timedelta(days=random.randint(7, 60)),
                        justification=f"Emergency procurement for {fac.name}",
                    )
                    # Add 2-3 items to each request
                    for ri in random.sample(self.resource_items, min(2, len(self.resource_items))):
                        qty = random.randint(10, 500)
                        try:
                            ProcurementItem.objects.create(
                                procurement_request=pr,
                                resource_item=ri,
                                quantity_requested=qty,
                                unit_cost=ri.unit_cost,
                                total_cost=ri.unit_cost * qty,
                            )
                        except Exception:
                            pass
                    pr_count += 1
                except Exception as e:
                    self.stdout.write(f"    ProcurementRequest skip: {e}")
            self.stdout.write(f"    Procurement Requests: {pr_count}")
        except Exception as e:
            self.stdout.write(f"    ProcurementRequest section error: {e}")

        # ── Demand Forecasts ──────────────────────────────────────────────────
        try:
            from resources.models import DemandForecast
            df_count = 0
            for item in self.resource_items[:5]:
                for loc in locs[:3]:
                    try:
                        DemandForecast.objects.create(
                            resource_item=item,
                            location=loc,
                            forecast_date=date.today(),
                            forecast_period_days=30,
                            predicted_demand=random.randint(100, 10000),
                            confidence_level=Decimal(str(rand_decimal(70.0, 95.0))),
                            forecast_model="XGBoost Demand Predictor v1.2",
                            is_current=True,
                        )
                        df_count += 1
                    except Exception:
                        pass
            self.stdout.write(f"    Demand Forecasts: {df_count}")
        except Exception as e:
            self.stdout.write(f"    DemandForecast section error: {e}")

    # =========================================================================
    # 7. COMMUNICATIONS
    # =========================================================================

    def _seed_communications(self):
        try:
            from communications.models import MessageTemplate, Campaign
        except ImportError:
            self.stdout.write(self.style.WARNING("    communications models not importable — skipped."))
            return

        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()

        # template_type choices: SMS, EMAIL, PUSH, ALERT, REMINDER, CONFIRMATION, BROADCAST
        template_specs = [
            dict(name="Outbreak Alert SMS",      template_type="ALERT",    language="en",
                 subject="", body="ALERT: {{disease}} outbreak in {{location}}. Seek help immediately."),
            dict(name="Quarantine Notice",        template_type="ALERT",    language="en",
                 subject="", body="QUARANTINE: You are a {{disease}} contact. Stay home {{days}} days."),
            dict(name="Health Advisory Email",    template_type="EMAIL",    language="en",
                 subject="Health Advisory: {{disease}} in {{location}}",
                 body="Dear {{name}},\n\nAdvisory for {{disease}} in {{location}}.\n\nOryxShield Team"),
            dict(name="Vaccination Reminder",     template_type="REMINDER", language="en",
                 subject="", body="REMINDER: {{vaccine}} vaccination on {{date}} at {{location}}."),
            dict(name="Test Result Notification", template_type="SMS",      language="en",
                 subject="", body="Your {{test_type}} result is ready. Contact {{clinic}}."),
        ]
        self.templates = []
        for spec in template_specs:
            try:
                tmpl, _ = MessageTemplate.objects.get_or_create(
                    name=spec["name"],
                    defaults={
                        "template_type": spec["template_type"],
                        "language": spec["language"],
                        "subject": spec.get("subject", ""),
                        "body": spec["body"],
                        "variables": ["disease", "location", "name"],
                        "is_active": True,
                    },
                )
                self.templates.append(tmpl)
            except Exception as e:
                self.stdout.write(f"    Template skip: {e}")
        self.stdout.write(f"    Message Templates: {len(self.templates)}")

        # campaign_type choices: AWARENESS, VACCINATION, TESTING, PREVENTION, OUTBREAK, EDUCATION
        campaign_specs = [
            dict(name="Cholera Prevention Campaign — Erongo Coast", campaign_type="PREVENTION", status="ACTIVE"),
            dict(name="COVID-19 Booster Vaccination Drive",    campaign_type="VACCINATION", status="ACTIVE"),
            dict(name="Malaria Awareness Week",                campaign_type="AWARENESS",  status="COMPLETED"),
            dict(name="Hand Hygiene Public Education",         campaign_type="EDUCATION",  status="DRAFT"),
            dict(name="Ebola Risk Communication",              campaign_type="OUTBREAK",   status="ACTIVE"),
        ]
        camp_count = 0
        for i, spec in enumerate(campaign_specs):
            try:
                Campaign.objects.get_or_create(
                    name=spec["name"],
                    defaults={
                        "campaign_type": spec["campaign_type"],
                        "description": f"Public health campaign: {spec['name']}",
                        "status": spec["status"],
                        "campaign_manager": admin,
                        "start_date": timezone.now() - timedelta(days=random.randint(0, 30)),
                        "end_date": timezone.now() + timedelta(days=random.randint(14, 90)),
                        "key_messages": ["Stay safe", "Seek treatment early", "Report symptoms"],
                        "channels": ["SMS", "RADIO", "SOCIAL"],
                        "target_reach": random.randint(10000, 500000),
                        "actual_reach": random.randint(0, 100000),
                        "budget": Decimal(str(rand_decimal(5000.0, 100000.0))),
                        "spent": Decimal(str(rand_decimal(0.0, 50000.0))),
                    },
                )
                camp_count += 1
            except Exception as e:
                self.stdout.write(f"    Campaign skip: {e}")
        self.stdout.write(f"    Campaigns: {camp_count}")

        # ── Contact Lists ─────────────────────────────────────────────────────
        try:
            from communications.models import ContactList
            from core.models import Location as Loc
            locs_comm = list(Loc.objects.filter(is_deleted=False))
            cl_specs = [
                ("Healthcare Workers — Windhoek",   "NA-KHO"),
                ("Community Health Volunteers",    "NA-KHO"),
                ("Laboratory Staff Network",       "KE"),
                ("District Health Officers",       "KE"),
                ("Media & Press Contacts",         "KE"),
                ("Cross-border Alert Network",     "KE"),
            ]
            cl_count = 0
            for cl_name, loc_code in cl_specs:
                loc = Loc.objects.filter(code=loc_code).first() or (locs_comm[0] if locs_comm else None)
                try:
                    ContactList.objects.get_or_create(  # noqa
                        name=cl_name,
                        defaults={
                            "description": f"Contact list: {cl_name}",
                            "owner": admin,
                            "location": loc,
                            "contacts": [
                                {"name": f"Contact {i}", "phone": f"+264810{random.randint(100000, 999999)}", "email": f"c{i}@oryxshield.gov.na"}
                                for i in range(random.randint(5, 20))
                            ],
                            "tags": ["health", "emergency"],
                            "is_active": True,
                        },
                    )
                    cl_count += 1
                except Exception as e:
                    self.stdout.write(f"    ContactList skip: {e}")
            self.stdout.write(f"    Contact Lists: {cl_count}")
        except Exception as e:
            self.stdout.write(f"    ContactList section error: {e}")

        # ── Broadcasts ────────────────────────────────────────────────────────
        try:
            from communications.models import Broadcast
            campaigns_qs = list(Campaign.objects.all()[:3])
            tmpl_qs = list(MessageTemplate.objects.all()[:3]) if hasattr(MessageTemplate, 'objects') else []
            bc_count = 0
            for i in range(5):
                try:
                    camp = campaigns_qs[i % len(campaigns_qs)] if campaigns_qs else None
                    tmpl = tmpl_qs[i % len(tmpl_qs)] if tmpl_qs else None
                    loc_bc = locs_comm[i % len(locs_comm)] if locs_comm else None
                    bc = Broadcast.objects.create(
                        campaign=camp,
                        template=tmpl,
                        title=f"Emergency Broadcast #{i+1}: Public Health Advisory",
                        message_content=f"ADVISORY: Monitor symptoms and report to nearest health facility. Broadcast #{i+1}.",
                        channels=random.sample(["SMS", "EMAIL", "PUSH", "RADIO"], k=random.randint(1, 3)),
                        target_criteria={"priority": "HIGH"},
                        status=random.choice(["DRAFT", "SCHEDULED", "SENT"]),
                    )
                    if loc_bc:
                        bc.target_locations.add(loc_bc)
                    bc_count += 1
                except Exception as e:
                    self.stdout.write(f"    Broadcast skip: {e}")
            self.stdout.write(f"    Broadcasts: {bc_count}")
        except Exception as e:
            self.stdout.write(f"    Broadcast section error: {e}")

        # ── Public Announcements ──────────────────────────────────────────────
        try:
            from communications.models import PublicAnnouncement
            pa_specs = [
                dict(title="Cholera Outbreak Advisory — Erongo Region",       atype="HEALTH_ALERT",    featured=True),
                dict(title="COVID-19 Booster Vaccine Now Available",            atype="VACCINATION",     featured=True),
                dict(title="Malaria Prevention Tips for Rainy Season",          atype="HEALTH_TIP",      featured=False),
                dict(title="Travel Advisory: Ebola Risk Zones in DRC",          atype="TRAVEL_ADVISORY", featured=True),
                dict(title="Mass Cholera Vaccination Campaign — Register Now",  atype="VACCINATION",     featured=False),
                dict(title="Emergency Water Quality Warning — Lake Victoria",   atype="HEALTH_ALERT",    featured=True),
            ]
            pa_count = 0
            for spec in pa_specs:
                try:
                    from django.utils.text import slugify
                    slug = slugify(spec["title"])[:349]
                    pa, created = PublicAnnouncement.objects.get_or_create(
                        slug=slug,
                        defaults={
                            "title": spec["title"],
                            "announcement_type": spec["atype"],
                            "content": f"Full advisory content for: {spec['title']}. Please follow all public health guidelines.",
                            "summary": f"Summary: {spec['title'][:100]}",
                            "author": admin,
                            "is_published": True,
                            "publish_date": days_ago(random.randint(0, 30)),
                            "expiry_date": timezone.now() + timedelta(days=30),
                            "is_featured": spec["featured"],
                            "display_priority": random.randint(1, 10),
                        },
                    )
                    pa_count += 1
                except Exception as e:
                    self.stdout.write(f"    Announcement skip: {e}")
            self.stdout.write(f"    Public Announcements: {pa_count}")
        except Exception as e:
            self.stdout.write(f"    PublicAnnouncement section error: {e}")

        # ── Social Media Posts ────────────────────────────────────────────────
        try:
            from communications.models import SocialMediaPost
            camps_for_social = list(Campaign.objects.all()[:5])
            sm_count = 0
            platforms = ["TWITTER", "FACEBOOK", "INSTAGRAM", "WHATSAPP"]
            posts = [
                "URGENT: Cholera cases rising in Walvis Bay. Drink boiled water only. #PublicHealth",
                "COVID-19 booster vaccines available at all regional health centres. Get protected today!",
                "Malaria season is here. Sleep under insecticide-treated nets every night. #MalariaPrevention",
                "Contact tracing teams are active in Windhoek East. If contacted, please cooperate. #HealthSecurity",
                "Hand hygiene saves lives. Wash hands with soap for at least 20 seconds. #WashYourHands",
            ]
            for i, content in enumerate(posts):
                camp = camps_for_social[i % len(camps_for_social)] if camps_for_social else None
                try:
                    SocialMediaPost.objects.create(
                        platform=platforms[i % len(platforms)],
                        content=content,
                        campaign=camp,
                        hashtags=["#PublicHealth", "#OryxShield", "#HealthAlert"],
                        status=random.choice(["DRAFT", "PUBLISHED", "SCHEDULED"]),
                        scheduled_for=timezone.now() + timedelta(hours=random.randint(1, 48)) if random.random() > 0.5 else None,
                        likes=random.randint(0, 5000),
                        shares=random.randint(0, 1000),
                    )
                    sm_count += 1
                except Exception as e:
                    self.stdout.write(f"    SocialPost skip: {e}")
            self.stdout.write(f"    Social Media Posts: {sm_count}")
        except Exception as e:
            self.stdout.write(f"    SocialMediaPost section error: {e}")

    # =========================================================================
    # 8. ANALYTICS
    # =========================================================================

    def _seed_analytics(self):
        try:
            from analytics.models import (
                EpidemiologicalModel, SpatialAnalysis, TimeSeriesAnalysis,
                StatisticalReport, Dashboard,
            )
        except ImportError:
            self.stdout.write(self.style.WARNING("    analytics models not importable — skipped."))
            return

        from core.models import Location
        locs = list(Location.objects.filter(is_deleted=False))
        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()

        diseases = [
            ("A00", "Cholera"), ("B50", "Malaria"), ("U07.1", "COVID-19"),
            ("A98.4", "Ebola"), ("A15", "Tuberculosis"),
        ]

        # ── Epidemiological Models ────────────────────────────────────────────
        # model_type choices: SIR, SEIR, SIRS, SEIRS, SIS, CUSTOM
        model_types = ["SEIR", "SIR", "SIRS", "SEIRS"]
        epi_count = 0
        for i, (dc, dn) in enumerate(diseases[:4]):
            loc = locs[i % len(locs)]
            m_type = model_types[i % len(model_types)]
            beta = rand_decimal(0.1, 0.5)
            gamma = rand_decimal(0.05, 0.3)
            try:
                EpidemiologicalModel.objects.get_or_create(
                    name=f"{dn} {m_type} Model — {loc.name}",
                    defaults={
                        "model_type": m_type,
                        "disease_code": dc,
                        "disease_name": dn,
                        "location": loc,
                        "parameters": {"beta": beta, "gamma": gamma, "sigma": rand_decimal(0.1, 0.3)},
                        "initial_susceptible": random.randint(400000, 4000000),
                        "initial_infected": random.randint(10, 500),
                        "initial_recovered": 0,
                        "basic_reproduction_number": Decimal(str(round(beta / max(gamma, 0.01), 2))),
                        "simulation_days": 180,
                        "simulation_results": {
                            "days": list(range(0, 181, 10)),
                            "infected": [random.randint(10, 50000) for _ in range(19)],
                            "recovered": [random.randint(0, 40000) for _ in range(19)],
                            "susceptible": [random.randint(100000, 4000000) for _ in range(19)],
                        },
                        "is_validated": random.choice([True, False]),
                        "model_fit_score": Decimal(str(rand_decimal(60.0, 99.0))),
                        "created_by": admin,
                    },
                )
                epi_count += 1
            except Exception as e:
                self.stdout.write(f"    EpiModel skip: {e}")
        self.stdout.write(f"    Epi Models: {epi_count}")

        # ── Spatial Analyses ──────────────────────────────────────────────────
        # analysis_type choices: HOTSPOT, CLUSTERING, AUTOCORRELATION, KERNEL_DENSITY, SPATIAL_SCAN
        spatial_count = 0
        for i, (dc, dn) in enumerate(diseases[:3]):
            loc = locs[i % len(locs)]
            try:
                SpatialAnalysis.objects.get_or_create(
                    name=f"Spatial Analysis — {dn} — {loc.name}",
                    defaults={
                        "analysis_type": random.choice(["HOTSPOT", "CLUSTERING", "AUTOCORRELATION"]),
                        "disease_code": dc,
                        "disease_name": dn,
                        "location": loc,
                        "start_date": date.today() - timedelta(days=90),
                        "end_date": date.today(),
                        "morans_i": Decimal(str(rand_decimal(0.1, 0.8))),
                        "p_value": Decimal(str(rand_decimal(0.001, 0.05))),
                        "z_score": Decimal(str(rand_decimal(1.5, 4.0))),
                        "hotspot_count": random.randint(1, 10),
                        "cluster_count": random.randint(1, 5),
                        "performed_by": admin,
                    },
                )
                spatial_count += 1
            except Exception as e:
                self.stdout.write(f"    Spatial skip: {e}")
        self.stdout.write(f"    Spatial Analyses: {spatial_count}")

        # ── Time Series Analyses ──────────────────────────────────────────────
        # analysis_type choices: TREND, SEASONALITY, FORECASTING, CHANGE_POINT, DECOMPOSITION
        # trend_direction choices: INCREASING, DECREASING, STABLE, FLUCTUATING
        ts_count = 0
        for i, (dc, dn) in enumerate(diseases[:3]):
            loc = locs[i % len(locs)]
            try:
                TimeSeriesAnalysis.objects.get_or_create(
                    name=f"Time Series — {dn} — {loc.name}",
                    defaults={
                        "analysis_type": random.choice(["TREND", "SEASONALITY", "FORECASTING"]),
                        "disease_code": dc,
                        "disease_name": dn,
                        "location": loc,
                        "start_date": date.today() - timedelta(days=180),
                        "end_date": date.today(),
                        "trend_direction": random.choice(["INCREASING", "DECREASING", "STABLE", "FLUCTUATING"]),
                        "trend_strength": Decimal(str(rand_decimal(30.0, 95.0))),
                        "has_seasonality": random.choice([True, False]),
                        "seasonal_period": random.choice([7, 14, 28, 52]),
                        "forecast_days": 30,
                        "mae": Decimal(str(rand_decimal(1.0, 20.0))),
                        "rmse": Decimal(str(rand_decimal(2.0, 30.0))),
                        "mape": Decimal(str(rand_decimal(5.0, 25.0))),
                        "performed_by": admin,
                    },
                )
                ts_count += 1
            except Exception as e:
                self.stdout.write(f"    TimeSeries skip: {e}")
        self.stdout.write(f"    Time Series Analyses: {ts_count}")

        # ── Statistical Reports ───────────────────────────────────────────────
        # report_type choices: DESCRIPTIVE, INFERENTIAL, COMPARATIVE, CORRELATION, REGRESSION
        # no single location FK — uses M2M locations; no summary field, use executive_summary
        report_specs = [
            dict(title="Weekly Descriptive Analysis — OryxShield",  report_type="DESCRIPTIVE",  published=True),
            dict(title="Monthly Comparative Disease Burden",        report_type="COMPARATIVE",  published=True),
            dict(title="Cholera Correlation Analysis",              report_type="CORRELATION",  published=True),
            dict(title="COVID-19 Regression Analysis",              report_type="REGRESSION",   published=False),
        ]
        sr_count = 0
        for spec in report_specs:
            try:
                StatisticalReport.objects.get_or_create(
                    title=spec["title"],
                    defaults={
                        "report_type": spec["report_type"],
                        "disease_codes": ["A00", "B50", "U07.1"],
                        "start_date": date.today() - timedelta(days=30),
                        "end_date": date.today(),
                        "executive_summary": f"Statistical analysis: {spec['title']}",
                        "key_findings": ["Case counts rising", "CFR stable", "Spread increasing"],
                        "is_published": spec["published"],
                        "published_at": timezone.now() - timedelta(days=1) if spec["published"] else None,
                        "author": admin,
                    },
                )
                sr_count += 1
            except Exception as e:
                self.stdout.write(f"    StatReport skip: {e}")
        self.stdout.write(f"    Statistical Reports: {sr_count}")

        # ── Dashboards ────────────────────────────────────────────────────────
        # No dashboard_type field; owner (FK) not created_by
        dash_specs = [
            "Executive Situation Room",
            "Epidemiological Dashboard",
            "Operations Command Centre",
        ]
        dash_count = 0
        for dash_name in dash_specs:
            try:
                Dashboard.objects.get_or_create(
                    name=dash_name,
                    defaults={
                        "description": f"Real-time {dash_name} for OryxShield",
                        "is_active": True,
                        "is_public": True,
                        "widgets": [{"type": "map"}, {"type": "alerts"}, {"type": "epi_curve"}],
                        "layout": {"cols": 3, "rows": 2},
                        "owner": admin,
                        "auto_refresh": True,
                        "refresh_interval_minutes": 5,
                    },
                )
                dash_count += 1
            except Exception as e:
                self.stdout.write(f"    Dashboard skip: {e}")
        self.stdout.write(f"    Dashboards: {dash_count}")

        # ── Indicators ────────────────────────────────────────────────────────
        try:
            from analytics.models import Indicator, IndicatorValue, ReportTemplate, DataExport
            ind_specs = [
                dict(code="CFR-001",  name="Case Fatality Rate",            ind_type="EPIDEMIOLOGICAL", unit="%",          freq="WEEKLY",   target=2.0,  direction="DECREASE"),
                dict(code="IR-001",   name="Incidence Rate per 100k",       ind_type="EPIDEMIOLOGICAL", unit="per 100,000", freq="WEEKLY",   target=50.0, direction="DECREASE"),
                dict(code="VAX-001",  name="Vaccination Coverage Rate",     ind_type="OPERATIONAL",     unit="%",          freq="MONTHLY",  target=80.0, direction="INCREASE"),
                dict(code="LAB-001",  name="Lab Test Positivity Rate",      ind_type="QUALITY",         unit="%",          freq="DAILY",    target=5.0,  direction="DECREASE"),
                dict(code="RESP-001", name="Response Time to Alert (hours)",ind_type="OPERATIONAL",     unit="hours",      freq="DAILY",    target=2.0,  direction="DECREASE"),
                dict(code="BED-001",  name="Hospital Bed Occupancy Rate",   ind_type="CAPACITY",        unit="%",          freq="DAILY",    target=70.0, direction="DECREASE"),
                dict(code="CT-001",   name="Contact Tracing Completion %",  ind_type="OUTCOME",         unit="%",          freq="WEEKLY",   target=90.0, direction="INCREASE"),
                dict(code="PPE-001",  name="PPE Stock Coverage (days)",     ind_type="CAPACITY",        unit="days",       freq="WEEKLY",   target=30.0, direction="INCREASE"),
            ]
            self.indicators = []
            for spec in ind_specs:
                try:
                    ind, _ = Indicator.objects.get_or_create(
                        code=spec["code"],
                        defaults={
                            "name": spec["name"],
                            "indicator_type": spec["ind_type"],
                            "description": f"Health indicator: {spec['name']}",
                            "definition": f"Measures {spec['name']} across all active surveillance locations.",
                            "calculation_method": f"Calculated weekly from surveillance data aggregates.",
                            "data_source": "DHIS2 / OryxShield Surveillance Module",
                            "unit_of_measure": spec["unit"],
                            "reporting_frequency": spec["freq"],
                            "target_value": Decimal(str(spec["target"])),
                            "target_direction": spec["direction"],
                            "is_active": True,
                        },
                    )
                    self.indicators.append(ind)
                except Exception as e:
                    self.stdout.write(f"    Indicator skip: {e}")
            self.stdout.write(f"    Indicators: {len(self.indicators)}")

            # ── Indicator Values ──────────────────────────────────────────────
            iv_count = 0
            for ind in self.indicators:
                for loc in locs[:4]:
                    for week in range(8):
                        period_start = date.today() - timedelta(weeks=week+1)
                        period_end   = period_start + timedelta(days=6)
                        val = Decimal(str(rand_decimal(0.5, float(ind.target_value or 10) * 1.5)))
                        try:
                            IndicatorValue.objects.get_or_create(
                                indicator=ind,
                                location=loc,
                                period_start=period_start,
                                period_end=period_end,
                                defaults={
                                    "value": val,
                                    "numerator": Decimal(str(rand_decimal(1, 1000))),
                                    "denominator": Decimal(str(rand_decimal(100, 100000))),
                                    "target_achieved": bool(
                                        (val <= ind.target_value if ind.target_direction == "DECREASE" else val >= (ind.target_value or 0))
                                        if ind.target_value else None
                                    ),
                                    "data_quality_score": random.randint(60, 100),
                                },
                            )
                            iv_count += 1
                        except Exception:
                            pass
            self.stdout.write(f"    Indicator Values: {iv_count}")

            # ── Report Templates ──────────────────────────────────────────────
            rt_specs = [
                dict(name="WHO Situation Report Template",  rt_type="WHO_SITREP", fmt="PDF"),
                dict(name="IHR Event Report Template",      rt_type="IHR",        fmt="DOCX"),
                dict(name="Africa CDC Weekly Template",     rt_type="AFRICA_CDC", fmt="PDF"),
                dict(name="Custom Outbreak Report",         rt_type="CUSTOM",     fmt="EXCEL"),
            ]
            rt_count = 0
            for spec in rt_specs:
                try:
                    rt, _ = ReportTemplate.objects.get_or_create(
                        name=spec["name"],
                        defaults={
                            "template_type": spec["rt_type"],
                            "description": f"Standard {spec['rt_type']} reporting template",
                            "output_format": spec["fmt"],
                            "sections": [
                                {"title": "Executive Summary", "order": 1},
                                {"title": "Epidemiological Situation", "order": 2},
                                {"title": "Response Actions", "order": 3},
                                {"title": "Recommendations", "order": 4},
                            ],
                            "is_active": True,
                            "created_by": admin,
                        },
                    )
                    if self.indicators:
                        rt.required_indicators.set(random.sample(self.indicators, min(3, len(self.indicators))))
                    rt_count += 1
                except Exception as e:
                    self.stdout.write(f"    ReportTemplate skip: {e}")
            self.stdout.write(f"    Report Templates: {rt_count}")

            # ── Data Exports ──────────────────────────────────────────────────
            de_count = 0
            export_formats = ["CSV", "EXCEL", "JSON"]
            export_statuses = ["COMPLETED", "COMPLETED", "COMPLETED", "COMPLETED", "FAILED"]
            export_types = ["health_data", "risk_scores", "alerts", "reports"]
            for i in range(10):
                try:
                    DataExport.objects.create(
                        name=f"Export {i+1} — {export_types[i % len(export_types)].replace('_', ' ').title()}",
                        data_type=random.choice(export_types),
                        export_format=random.choice(export_formats),
                        status=random.choice(export_statuses),
                        requested_by=admin,
                        filters={"date_from": str(date.today() - timedelta(days=30)), "date_to": str(date.today())},
                        row_count=random.randint(100, 50000) if i < 7 else None,
                        file_size=random.randint(1024, 10 * 1024 * 1024) if i < 7 else None,
                    )
                    de_count += 1
                except Exception as e:
                    self.stdout.write(f"    DataExport skip: {e}")
            self.stdout.write(f"    Data Exports: {de_count}")
        except Exception as e:
            self.stdout.write(f"    Analytics extended section error: {e}")

    # =========================================================================
    # 9. OPERATIONS
    # =========================================================================

    def _seed_operations(self):
        try:
            from operations.models import (
                Case, Contact, TestingCenter, TestingAppointment,
                VaccinationCampaign, QuarantineFacility,
            )
        except ImportError:
            self.stdout.write(self.style.WARNING("    operations models not importable — skipped."))
            return

        from core.models import Location
        locs = list(Location.objects.filter(is_deleted=False))
        admin = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first() or User.objects.first()
        users = list(User.objects.all())

        diseases = [
            ("A00", "Cholera"), ("B50", "Malaria"), ("U07.1", "COVID-19"),
        ]

        # ── Testing Centers ───────────────────────────────────────────────────
        # Requires unique `code` field; no center_type/is_24_hour/status fields
        self.testing_centers = []
        tc_specs = [
            dict(name="Windhoek City Testing Centre", code="TC-WDH-01", loc_code="NA-KHO"),
            dict(name="Walvis Bay Port Testing Centre",    code="TC-WLV-01", loc_code="NA-ERO"),
            dict(name="Windhoek Central Hospital Laboratory", code="TC-WCH-01", loc_code="NA-WCH"),
            dict(name="Kampala Airport Screening",        code="TC-KLA-01", loc_code="UG-KLA"),
        ]
        for spec in tc_specs:
            loc = Location.objects.filter(code=spec["loc_code"]).first() or locs[0]
            try:
                tc, _ = TestingCenter.objects.get_or_create(
                    code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "location": loc,
                        "daily_capacity": random.randint(50, 500),
                        "current_load": random.randint(20, 300),
                        "contact_phone": "+264810000000",
                        "contact_email": "testing@oryxshield.gov.na",
                        "is_operational": True,
                        "managed_by": admin,
                        "test_types": ["PCR", "RDT", "ANTIBODY"],
                        "operating_hours": {"monday": "08:00-18:00", "friday": "08:00-18:00"},
                    },
                )
                self.testing_centers.append(tc)
            except Exception as e:
                self.stdout.write(f"    TestingCenter skip: {e}")
        self.stdout.write(f"    Testing Centers: {len(self.testing_centers)}")

        # ── Cases ──────────────────────────────────────────────────────────────
        # Fields: case_id (unique), patient_name, patient_age, patient_gender, patient_contact
        # classification: SUSPECT/PROBABLE/CONFIRMED/NOT_A_CASE; status: ACTIVE/RECOVERED/DECEASED/LOST_TO_FOLLOWUP
        self.cases = []
        used_case_ids = set()
        for idx in range(30):
            loc = random.choice(locs)
            dc, dn = random.choice(diseases)
            while True:
                case_id = f"CASE-{random.randint(10000, 99999)}"
                if case_id not in used_case_ids:
                    used_case_ids.add(case_id)
                    break
            try:
                case = Case.objects.create(
                    case_id=case_id,
                    patient_name=f"Patient {random.randint(1000, 9999)}",
                    patient_age=random.randint(1, 85),
                    patient_gender=random.choice(["M", "F"]),
                    patient_contact=f"+264{random.randint(700000000, 799999999)}",
                    disease_code=dc,
                    disease_name=dn,
                    location=loc,
                    classification=random.choice(["SUSPECT", "PROBABLE", "CONFIRMED"]),
                    status=random.choice(["ACTIVE", "RECOVERED"]),
                    symptom_onset_date=date.today() - timedelta(days=random.randint(1, 30)),
                    diagnosis_date=date.today() - timedelta(days=random.randint(0, 20)),
                    symptoms=["fever", "cough", "fatigue"][:random.randint(1, 3)],
                    clinical_notes=f"Case notes for {dn} in {loc.name}",
                    is_isolated=random.choice([True, False]),
                    assigned_to=random.choice(users),
                )
                self.cases.append(case)
            except Exception as e:
                self.stdout.write(f"    Case skip: {e}")
        self.stdout.write(f"    Cases: {len(self.cases)}")

        # ── Contacts ──────────────────────────────────────────────────────────
        # Fields: contact_id (unique), source_case, contact_name, contact_type, exposure_date, last_contact_date
        contacts_created = 0
        for case in self.cases[:15]:
            num_contacts = random.randint(1, 4)
            for j in range(num_contacts):
                try:
                    onset = case.symptom_onset_date or date.today()
                    Contact.objects.create(
                        contact_id=f"CON-{case.case_id}-{j+1}",
                        source_case=case,
                        contact_name=f"Contact {random.randint(1000, 9999)}",
                        contact_age=random.randint(1, 80),
                        contact_gender=random.choice(["M", "F"]),
                        contact_phone=f"+264{random.randint(700000000, 799999999)}",
                        location=case.location,
                        contact_type=random.choice(["HOUSEHOLD", "WORKPLACE", "SOCIAL"]),
                        exposure_date=onset,
                        last_contact_date=date.today() - timedelta(days=random.randint(0, 5)),
                        status=random.choice(["IDENTIFIED", "UNDER_MONITORING", "CLEARED"]),
                        assigned_to=admin,
                    )
                    contacts_created += 1
                except Exception:
                    pass
        self.stdout.write(f"    Contacts: {contacts_created}")

        # ── Testing Appointments ──────────────────────────────────────────────
        # Fields: appointment_id (unique), testing_center, patient_name, patient_contact,
        #         appointment_date (DateField), appointment_time (TimeField), test_type,
        #         status, result
        import datetime as _dt
        used_appt_ids = set()
        appt_count = 0
        for _ in range(25):
            if not self.testing_centers:
                break
            tc = random.choice(self.testing_centers)
            case = random.choice(self.cases) if self.cases and random.random() > 0.5 else None
            result = random.choice(["POSITIVE", "NEGATIVE", "PENDING", "INCONCLUSIVE"])
            while True:
                appt_id = f"APT-{random.randint(10000, 99999)}"
                if appt_id not in used_appt_ids:
                    used_appt_ids.add(appt_id)
                    break
            try:
                appt_date = date.today() + timedelta(days=random.randint(-5, 5))
                TestingAppointment.objects.create(
                    appointment_id=appt_id,
                    testing_center=tc,
                    case=case,
                    patient_name=f"Patient {random.randint(1000, 9999)}",
                    patient_contact=f"+264{random.randint(700000000, 799999999)}",
                    appointment_date=appt_date,
                    appointment_time=_dt.time(random.randint(8, 16), 0),
                    test_type=random.choice(["PCR", "RDT", "ANTIBODY"]),
                    status="COMPLETED" if result != "PENDING" else "SCHEDULED",
                    result=result,
                    lab_reference=f"LAB-{random.randint(10000, 99999)}" if result != "PENDING" else "",
                )
                appt_count += 1
            except Exception:
                pass
        self.stdout.write(f"    Testing Appointments: {appt_count}")

        # ── Quarantine Facilities ─────────────────────────────────────────────
        # Requires unique `code`; no `managed_by` field on this model
        qf_specs = [
            dict(name="Windhoek Quarantine Centre — Khomasdal", code="QF-WDH-01", loc_code="NA-KHO", capacity=200),
            dict(name="Walvis Bay Isolation Facility",        code="QF-WLV-01", loc_code="NA-ERO", capacity=100),
            dict(name="Kampala Holding Centre",              code="QF-KLA-01", loc_code="UG-KLA", capacity=150),
        ]
        qf_count = 0
        for spec in qf_specs:
            loc = Location.objects.filter(code=spec["loc_code"]).first() or locs[0]
            try:
                QuarantineFacility.objects.get_or_create(
                    code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "facility_type": "QUARANTINE",
                        "location": loc,
                        "total_capacity": spec["capacity"],
                        "current_occupancy": random.randint(0, spec["capacity"] // 2),
                        "is_operational": True,
                        "contact_phone": "+264810111222",
                        "contact_person": "Facility Manager",
                    },
                )
                qf_count += 1
            except Exception as e:
                self.stdout.write(f"    QFacility skip: {e}")
        self.stdout.write(f"    Quarantine Facilities: {qf_count}")

        # ── Vaccination Campaigns ──────────────────────────────────────────────
        # Requires unique `campaign_code`; target_locations is M2M; campaign_manager not managed_by
        # status choices: PLANNING, ACTIVE, PAUSED, COMPLETED, CANCELLED
        vax_specs = [
            dict(name="COVID-19 Booster Campaign — Windhoek", code="VAX-COV-001", vaccine="COVID-19 mRNA Booster",
                 disease="COVID-19", loc_code="NA-KHO", status="ACTIVE"),
            dict(name="Cholera OCV — Erongo Coast",           code="VAX-CHO-001", vaccine="Cholera OCV",
                 disease="Cholera", loc_code="NA-ERO", status="ACTIVE"),
            dict(name="Yellow Fever Drive",                  code="VAX-YFV-001", vaccine="Yellow Fever 17D",
                 disease="Yellow Fever", loc_code="NA-KHO", status="COMPLETED"),
            dict(name="Typhoid Mass Vaccination — Oshana Region", code="VAX-TYP-001", vaccine="Typhoid Vi Conjugate",
                 disease="Typhoid Fever", loc_code="NA-OSH", status="PLANNING"),
        ]
        vc_count = 0
        for spec in vax_specs:
            loc = Location.objects.filter(code=spec["loc_code"]).first() or locs[0]
            target = random.randint(10000, 500000)
            vacc = int(target * rand_decimal(0.3, 0.9)) if spec["status"] not in ("PLANNING",) else 0
            try:
                vc, created = VaccinationCampaign.objects.get_or_create(
                    campaign_code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "vaccine_name": spec["vaccine"],
                        "vaccine_type": "Injectable",
                        "target_disease": spec["disease"],
                        "target_population": target,
                        "people_vaccinated": vacc,
                        "doses_administered": vacc,
                        "start_date": date.today() - timedelta(days=random.randint(0, 30)),
                        "end_date": date.today() + timedelta(days=random.randint(7, 60)),
                        "status": spec["status"],
                        "campaign_manager": admin,
                    },
                )
                if created:
                    vc.target_locations.add(loc)
                vc_count += 1
            except Exception as e:
                self.stdout.write(f"    VaxCampaign skip: {e}")
        self.stdout.write(f"    Vaccination Campaigns: {vc_count}")

        # ── Contact Monitoring ────────────────────────────────────────────────
        try:
            from operations.models import ContactMonitoring, Contact as OpContact
            contacts_for_mon = list(OpContact.objects.filter(status="UNDER_MONITORING")[:20])
            cm_count = 0
            for contact in contacts_for_mon:
                for day in range(random.randint(1, 7)):
                    mon_date = date.today() - timedelta(days=day)
                    has_symp = random.random() < 0.15
                    try:
                        ContactMonitoring.objects.get_or_create(
                            contact=contact,
                            monitoring_date=mon_date,
                            defaults={
                                "has_symptoms": has_symp,
                                "symptoms": ["fever", "cough"] if has_symp else [],
                                "temperature": Decimal(str(rand_decimal(36.0, 39.5 if has_symp else 37.5))),
                                "is_reachable": random.random() > 0.1,
                                "is_compliant": random.random() > 0.15,
                                "notes": "Daily contact monitoring check",
                                "action_taken": "Alert sent to health facility" if has_symp else "",
                                "monitored_by": admin,
                            },
                        )
                        cm_count += 1
                    except Exception:
                        pass
            self.stdout.write(f"    Contact Monitoring Records: {cm_count}")
        except Exception as e:
            self.stdout.write(f"    ContactMonitoring section error: {e}")

        # ── Vaccination Records ────────────────────────────────────────────────
        try:
            from operations.models import VaccinationRecord, VaccinationCampaign as VC
            vax_campaigns = list(VC.objects.all()[:4])
            vr_count = 0
            locs_ops = list(Location.objects.filter(is_deleted=False))
            for camp in vax_campaigns:
                for j in range(random.randint(5, 15)):
                    pat_id = f"PAT-{random.randint(100000, 999999)}"
                    try:
                        VaccinationRecord.objects.create(
                            record_id=f"VAX-{camp.campaign_code}-{j+1}-{random.randint(1000, 9999)}",
                            campaign=camp,
                            patient_name=f"Patient {random.randint(1000, 9999)}",
                            patient_age=random.randint(1, 75),
                            patient_gender=random.choice(["M", "F"]),
                            patient_id_number=pat_id,
                            patient_contact=f"+264{random.randint(700000000, 799999999)}",
                            location=random.choice(locs_ops),
                            vaccination_site=f"Site {random.randint(1, 10)}",
                            vaccine_name=camp.vaccine_name,
                            vaccine_batch=f"BATCH-{random.randint(10000, 99999)}",
                            dose_number=random.choice([1, 1, 1, 2]),
                            vaccination_date=date.today() - timedelta(days=random.randint(0, 30)),
                            adverse_event_reported=random.random() < 0.05,
                        )
                        vr_count += 1
                    except Exception:
                        pass
            self.stdout.write(f"    Vaccination Records: {vr_count}")
        except Exception as e:
            self.stdout.write(f"    VaccinationRecord section error: {e}")

        # ── Quarantine Records ─────────────────────────────────────────────────
        try:
            from operations.models import QuarantineRecord, QuarantineFacility as QF
            qfs = list(QF.objects.all())
            cases_for_qr = list(Case.objects.filter(is_isolated=True)[:10])
            qr_count = 0
            qr_statuses = ["QUARANTINED", "RELEASED", "TRANSFERRED"]
            for i, case in enumerate(cases_for_qr):
                if not qfs:
                    break
                qf = qfs[i % len(qfs)]
                admit_date = date.today() - timedelta(days=random.randint(1, 14))
                try:
                    QuarantineRecord.objects.create(
                        record_id=f"QR-{case.case_id}-{i+1}",
                        facility=qf,
                        individual_name=case.patient_name,
                        individual_contact=case.patient_contact or "",
                        case=case,
                        admission_date=admit_date,
                        expected_release_date=admit_date + timedelta(days=14),
                        actual_release_date=admit_date + timedelta(days=random.randint(7, 14)) if random.random() > 0.5 else None,
                        status=random.choice(qr_statuses),
                    )
                    qr_count += 1
                except Exception as e:
                    self.stdout.write(f"    QuarantineRecord skip: {e}")
            self.stdout.write(f"    Quarantine Records: {qr_count}")
        except Exception as e:
            self.stdout.write(f"    QuarantineRecord section error: {e}")

        # ── Increase Health Data volume to 300 records ────────────────────────
        try:
            from surveillance.models import HealthData, DataSource, DiseaseProfile
            ds_list = list(DataSource.objects.all())
            dp_list = list(DiseaseProfile.objects.all())
            hd_extra = 0
            for _ in range(240):
                if not ds_list or not dp_list or not locs_ops:
                    break
                ds = random.choice(ds_list)
                dp = random.choice(dp_list)
                loc = random.choice(locs_ops)
                HealthData.objects.create(
                    data_source=ds,
                    location=loc,
                    disease_code=dp.disease_code,
                    disease_name=dp.disease_name,
                    data_type=random.choice(["CASE", "LAB_RESULT", "ADMISSION", "DEATH"]),
                    date_recorded=timezone.now() - timedelta(days=random.randint(0, 180)),
                    age=random.randint(1, 85),
                    gender=random.choice(["M", "F", "U"]),
                    severity=random.choice(["MILD", "MODERATE", "SEVERE"]),
                    outcome=random.choice(["RECOVERED", "HOSPITALISED", "UNKNOWN"]),
                    symptoms=["fever", "fatigue"][:random.randint(1, 2)],
                    test_result=random.choice(["POSITIVE", "NEGATIVE", "PENDING"]),
                    processed=True,
                )
                hd_extra += 1
            self.stdout.write(f"    Extra Health Data records: {hd_extra}")
        except Exception as e:
            self.stdout.write(f"    Extra HealthData section error: {e}")

    # =========================================================================
    # 10. INTEGRATIONS
    # =========================================================================

    def _seed_integrations(self):
        from integrations.models import (
            ExternalSystem, IntegrationJob, APIKey, DataTransfer, DataMapping,
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin = (
            User.objects.filter(username='admin').first()
            or User.objects.filter(is_superuser=True).first()
            or User.objects.first()
        )

        # ── External Systems ───────────────────────────────────────────────────
        systems_spec = [
            dict(name="WHO Disease Outbreak News",  system_code="WHO-DON",     system_type="DATA_SOURCE", base_url="https://www.who.int/api", auth_type="API_KEY",  health_status="HEALTHY"),
            dict(name="Africa CDC Integrated Surv", system_code="AFRCDC-ISS",  system_type="DATA_SOURCE", base_url="https://africacdc.org/api", auth_type="OAUTH2", health_status="HEALTHY"),
            dict(name="KEMRI Laboratory Network",   system_code="KEMRI-LAB",   system_type="LAB_SYSTEM",  base_url="https://kemri.gov.na/api", auth_type="BEARER",  health_status="DEGRADED"),
            dict(name="MOHSS Namibia DHIS2",            system_code="MOHSS-DHIS2",   system_type="DHIS2",       base_url="https://dhis2.health.gov.na", auth_type="BASIC", health_status="HEALTHY"),
            dict(name="UNICEF Situation Reports",   system_code="UNICEF-SR",   system_type="DATA_SOURCE", base_url="https://data.unicef.org/api", auth_type="API_KEY", health_status="HEALTHY"),
        ]
        self.int_systems = []
        for spec in systems_spec:
            sys_obj, _ = ExternalSystem.objects.get_or_create(
                system_code=spec["system_code"],
                defaults={
                    "name": spec["name"],
                    "system_type": spec["system_type"],
                    "description": f"Integration with {spec['name']}",
                    "base_url": spec["base_url"],
                    "auth_type": spec["auth_type"],
                    "credentials": {"key": "demo-key-xxxx"},
                    "configuration": {"timeout": 30, "retry": 3},
                    "sync_interval_minutes": random.choice([15, 30, 60, 120]),
                    "batch_size": random.choice([100, 250, 500]),
                    "is_active": True,
                    "sync_enabled": True,
                    "health_status": spec["health_status"],
                    "health_message": "All systems nominal" if spec["health_status"] == "HEALTHY" else "Intermittent delays",
                    "total_sync_count": random.randint(50, 500),
                    "successful_sync_count": random.randint(40, 480),
                },
            )
            self.int_systems.append(sys_obj)
        self.stdout.write(f"    External Systems: {len(self.int_systems)}")

        # ── Integration Jobs ───────────────────────────────────────────────────
        job_statuses = ["COMPLETED", "COMPLETED", "COMPLETED", "FAILED", "RUNNING"]
        job_types = ["FULL_SYNC", "INCREMENTAL", "INCREMENTAL", "FULL_SYNC", "VALIDATION"]
        job_count = 0
        for i, sys_obj in enumerate(self.int_systems):
            for j in range(2):
                try:
                    started = timezone.now() - timedelta(hours=random.randint(1, 48))
                    status = random.choice(job_statuses)
                    IntegrationJob.objects.get_or_create(
                        external_system=sys_obj,
                        job_type=job_types[(i + j) % len(job_types)],
                        started_at=started,
                        defaults={
                            "status": status,
                            "total_records": random.randint(100, 2000),
                            "processed_records": random.randint(80, 1900),
                            "successful_records": random.randint(70, 1800),
                            "failed_records": random.randint(0, 20),
                            "completed_at": started + timedelta(minutes=random.randint(2, 30)) if status != "RUNNING" else None,
                            "error_log": ["Connection timeout after 30s"] if status == "FAILED" else [],
                            "triggered_by": admin,
                            "job_id": uuid.uuid4(),
                        },
                    )
                    job_count += 1
                except Exception as e:
                    self.stdout.write(f"    Job skip: {e}")
        self.stdout.write(f"    Integration Jobs: {job_count}")

        # ── API Keys ──────────────────────────────────────────────────────────
        api_key_specs = [
            dict(name="Dashboard Read Access",     scope="READ",       rate_limit=1000),
            dict(name="Surveillance Data Ingestion",scope="WRITE",     rate_limit=500),
            dict(name="Analytics Export Key",      scope="READ",       rate_limit=200),
            dict(name="Mobile App Integration",    scope="READ_WRITE", rate_limit=2000),
            dict(name="Partner Portal Access",     scope="READ",       rate_limit=300),
        ]
        ak_count = 0
        for i, spec in enumerate(api_key_specs):
            try:
                APIKey.objects.get_or_create(
                    name=spec["name"],
                    defaults={
                        "key_prefix": f"lsp_{i+1:03d}",
                        "key_hash": f"hashed_key_{uuid.uuid4().hex[:32]}",
                        "description": f"API key: {spec['name']}",
                        "owner": admin,
                        "scope": spec["scope"],
                        "permissions": ["read", "list"],
                        "rate_limit": spec["rate_limit"],
                        "burst_limit": spec["rate_limit"] * 2,
                        "total_requests": random.randint(1000, 50000),
                        "successful_requests": random.randint(900, 49000),
                        "is_active": True,
                        "external_system": self.int_systems[i % len(self.int_systems)] if self.int_systems else None,
                    },
                )
                ak_count += 1
            except Exception as e:
                self.stdout.write(f"    APIKey skip: {e}")
        self.stdout.write(f"    API Keys: {ak_count}")

        # ── Data Transfers ─────────────────────────────────────────────────────
        dt_count = 0
        transfer_types = ["INBOUND", "OUTBOUND", "BIDIRECTIONAL"]
        entity_types = ["CASE", "LAB_RESULT", "HEALTH_DATA", "ALERT"]
        for i in range(10):
            src = self.int_systems[i % len(self.int_systems)] if self.int_systems else None
            tgt = self.int_systems[(i + 1) % len(self.int_systems)] if self.int_systems else None
            started = timezone.now() - timedelta(hours=random.randint(1, 72))
            status = random.choice(["COMPLETED", "COMPLETED", "FAILED", "IN_PROGRESS"])
            try:
                DataTransfer.objects.get_or_create(
                    transfer_id=f"TXN-{2026}-{i+1:05d}",
                    defaults={
                        "source_system": src,
                        "target_system": tgt,
                        "transfer_type": random.choice(transfer_types),
                        "entity_type": random.choice(entity_types),
                        "record_count": random.randint(50, 2000),
                        "data_size_bytes": random.randint(10000, 5000000),
                        "status": status,
                        "status_message": "Transfer completed successfully" if status == "COMPLETED" else "Connection reset",
                        "started_at": started,
                        "completed_at": started + timedelta(minutes=random.randint(1, 15)) if status == "COMPLETED" else None,
                        "transferred_records": random.randint(40, 1900),
                        "failed_records": random.randint(0, 50),
                        "initiated_by": admin,
                    },
                )
                dt_count += 1
            except Exception as e:
                self.stdout.write(f"    DataTransfer skip: {e}")
        self.stdout.write(f"    Data Transfers: {dt_count}")

        # ── Data Mappings ──────────────────────────────────────────────────────
        dm_count = 0
        mapping_specs = [
            dict(entity="CASE",        src="caseId",         tgt="case_id",       transform="DIRECT"),
            dict(entity="CASE",        src="patientAge",     tgt="age",           transform="TYPE_CAST"),
            dict(entity="CASE",        src="reportDate",     tgt="date_recorded", transform="DATE_FORMAT"),
            dict(entity="LAB_RESULT",  src="testCode",       tgt="disease_code",  transform="LOOKUP"),
            dict(entity="LAB_RESULT",  src="resultValue",    tgt="test_result",   transform="CONDITIONAL"),
            dict(entity="HEALTH_DATA", src="facility_code",  tgt="data_source_id",transform="LOOKUP"),
            dict(entity="ALERT",       src="alert_severity", tgt="severity",      transform="VALUE_MAP"),
            dict(entity="ALERT",       src="alert_date",     tgt="created_at",    transform="DATE_FORMAT"),
        ]
        for i, spec in enumerate(mapping_specs):
            sys_obj = self.int_systems[i % len(self.int_systems)] if self.int_systems else None
            try:
                DataMapping.objects.get_or_create(
                    external_system=sys_obj,
                    entity_type=spec["entity"],
                    source_field=spec["src"],
                    target_field=spec["tgt"],
                    defaults={
                        "transform_type": spec["transform"],
                        "transformation_rule": f"map_{spec['src']}_to_{spec['tgt']}",
                        "is_required": random.choice([True, False]),
                        "direction": "INBOUND",
                        "priority": i + 1,
                        "is_active": True,
                    },
                )
                dm_count += 1
            except Exception as e:
                self.stdout.write(f"    DataMapping skip: {e}")
        self.stdout.write(f"    Data Mappings: {dm_count}")

    # =========================================================================
    # 11. ESCALATION TRIGGERS & DATA QUALITY
    # =========================================================================

    def _seed_triggers_and_quality(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin = (
            User.objects.filter(username='admin').first()
            or User.objects.filter(is_superuser=True).first()
            or User.objects.first()
        )
        from core.models import Location as Loc
        locs = list(Loc.objects.filter(is_deleted=False))

        # ── Escalation Triggers ────────────────────────────────────────────────
        try:
            from response.models import EscalationTrigger, ResponseLevel
            levels = list(ResponseLevel.objects.all())
            trigger_specs = [
                dict(name="Case Fatality Rate >5%",    trigger_type="INDICATOR",  threshold=5.0,   eval_days=7,  disease_codes=["A98.4", "A00"]),
                dict(name="New Cases >100/day",        trigger_type="INDICATOR",  threshold=100.0, eval_days=1,  disease_codes=[]),
                dict(name="Healthcare System >80%",    trigger_type="CAPACITY",   threshold=80.0,  eval_days=3,  disease_codes=[]),
                dict(name="Cross-border Spread Alert", trigger_type="GEOGRAPHIC", threshold=3.0,   eval_days=14, disease_codes=["U07.1", "A98.4"]),
                dict(name="Lab Positivity >30%",       trigger_type="INDICATOR",  threshold=30.0,  eval_days=7,  disease_codes=[]),
            ]
            et_count = 0
            for i, spec in enumerate(trigger_specs):
                from_lvl = levels[max(0, i - 1)] if levels else None
                to_lvl   = levels[min(len(levels) - 1, i)] if levels else None
                try:
                    EscalationTrigger.objects.get_or_create(
                        name=spec["name"],
                        defaults={
                            "trigger_type": spec["trigger_type"],
                            "description": f"Auto-escalate when {spec['name']}",
                            "from_level": from_lvl,
                            "to_level": to_lvl,
                            "threshold_value": Decimal(str(spec["threshold"])),
                            "evaluation_period_days": spec["eval_days"],
                            "disease_codes": spec["disease_codes"],
                            "auto_escalate": True,
                            "is_active": True,
                        },
                    )
                    et_count += 1
                except Exception as e:
                    self.stdout.write(f"    EscalationTrigger skip: {e}")
            self.stdout.write(f"    Escalation Triggers: {et_count}")
        except Exception as e:
            self.stdout.write(f"    EscalationTrigger section error: {e}")

        # ── Data Quality Checks ────────────────────────────────────────────────
        try:
            from surveillance.models import DataQualityCheck, DataSource
            sources = list(DataSource.objects.all())
            check_types = ["COMPLETENESS", "CONSISTENCY", "ACCURACY", "TIMELINESS", "DUPLICATION"]
            statuses    = ["PASSED", "PASSED", "FAILED", "WARNING"]
            dq_count = 0
            for i in range(15):
                ds = sources[i % len(sources)] if sources else None
                if not ds:
                    break
                ctype = check_types[i % len(check_types)]
                records_checked = random.randint(100, 2000)
                pass_rate = rand_decimal(60.0, 99.9)
                records_passed  = int(records_checked * pass_rate / 100)
                records_failed  = records_checked - records_passed
                status = statuses[i % len(statuses)]
                try:
                    DataQualityCheck.objects.get_or_create(
                        data_source=ds,
                        check_type=ctype,
                        check_date=date.today() - timedelta(days=i),
                        defaults={
                            "records_checked": records_checked,
                            "records_passed": records_passed,
                            "records_failed": records_failed,
                            "pass_rate": Decimal(str(pass_rate)),
                            "status": status,
                            "issues": [
                                f"Missing values in {random.randint(1,5)} fields",
                                f"Duplicate records: {records_failed}",
                            ] if status != "PASSED" else [],
                        },
                    )
                    dq_count += 1
                except Exception as e:
                    self.stdout.write(f"    DataQualityCheck skip: {e}")
            self.stdout.write(f"    Data Quality Checks: {dq_count}")
        except Exception as e:
            self.stdout.write(f"    DataQualityCheck section error: {e}")
