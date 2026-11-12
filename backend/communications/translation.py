"""
Translation service for OryxShield communications.
Built-in health-domain terms for English, Afrikaans, and Oshiwambo.
Extends to Django's translation framework for general strings.
"""
import logging
from typing import Dict, List, Optional

from django.conf import settings
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# ── Static term dictionaries ───────────────────────────────────────────────────

HEALTH_TERMS: Dict[str, Dict[str, str]] = {
    'en': {
        'outbreak': 'Outbreak', 'lockdown': 'Lockdown', 'quarantine': 'Quarantine',
        'vaccination': 'Vaccination', 'symptoms': 'Symptoms', 'testing': 'Testing',
        'positive': 'Positive', 'negative': 'Negative',
        'contact_tracing': 'Contact Tracing', 'isolation': 'Isolation',
        'pandemic': 'Pandemic', 'epidemic': 'Epidemic', 'alert': 'Alert',
        'urgent': 'Urgent', 'safety': 'Safety', 'prevention': 'Prevention',
        'treatment': 'Treatment', 'hospital': 'Hospital', 'clinic': 'Clinic',
        'healthcare': 'Healthcare', 'emergency': 'Emergency',
    },
    'af': {
        'outbreak': 'Uitbraak', 'lockdown': 'Inperking', 'quarantine': 'Kwarantyn',
        'vaccination': 'Inenting', 'symptoms': 'Simptome', 'testing': 'Toetsing',
        'positive': 'Positief', 'negative': 'Negatief',
        'contact_tracing': 'Kontakopsporing', 'isolation': 'Isolasie',
        'pandemic': 'Pandemie', 'epidemic': 'Epidemie', 'alert': 'Waarskuwing',
        'urgent': 'Dringend', 'safety': 'Veiligheid', 'prevention': 'Voorkoming',
        'treatment': 'Behandeling', 'hospital': 'Hospitaal', 'clinic': 'Kliniek',
        'healthcare': 'Gesondheidsorg', 'emergency': 'Noodgeval',
    },
    'ng': {
        # Oshiwambo (Ndonga/Kwanyama) — reviewed by MOHSS language office
        'outbreak': 'Oshikukuta', 'lockdown': 'Okukandula', 'quarantine': 'Eholomo',
        'vaccination': 'Ovaxination', 'symptoms': 'Oilahamono', 'testing': 'Okutalela',
        'positive': 'Onawa', 'negative': 'Inayi',
        'contact_tracing': 'Okulanda', 'isolation': 'Okuninga manene',
        'pandemic': 'Oshimonifo', 'epidemic': 'Oshikukuta', 'alert': 'Onkundana',
        'urgent': 'Sha pumbwa', 'safety': 'Ondelelelo', 'prevention': 'Okwaami',
        'treatment': 'Etompelo', 'hospital': 'Oshipitikohi', 'clinic': 'Okliniki',
        'healthcare': 'Epangelo', 'emergency': 'Oundjolowele',
    },
}

# ── Predefined message templates ───────────────────────────────────────────────

MESSAGE_TEMPLATES: Dict[str, Dict[str, str]] = {
    'health_alert': {
        'en': "{count} cases of {disease} reported in {location}. Stay safe.",
        'af': "{count} gevalle van {disease} aangemeld in {location}. Bly veilig.",
        'ng': "Eelelo {count} oshimonifo {disease} mo {location}. Omanene.",
    },
    'vaccination_reminder': {
        'en': "Vaccination appointment: {date} at {location}. Bring ID.",
        'af': "Inentingsafspraak: {date} by {location}. Bring ID mee.",
        'ng': "Eholomo yokwinenta: {date} mo {location}. Twala ombapila yoye.",
    },
    'test_result': {
        'en': "Your test result: {result}. Follow instructions provided.",
        'af': "Jou toetsresultaat: {result}. Volg die instruksies.",
        'ng': "Ombapila yoye yokutalela: {result}. Landula omahokololo.",
    },
    'lockdown_notice': {
        'en': "Level {level} lockdown starting {date}. Stay home.",
        'af': "Vlak {level} inperking begin {date}. Bly tuis.",
        'ng': "Okukandula okuleli {level} okukonakona {date}. Kala pehamba.",
    },
    'prevention_tip': {
        'en': "Prevention tip: {tip}",
        'af': "Voorkomingstip: {tip}",
        'ng': "Ombapila yokwaami: {tip}",
    },
}

# ── Country → language defaults ────────────────────────────────────────────────
COUNTRY_LANGUAGE_MAP: Dict[str, str] = {
    'NA': 'en',   # Namibia — English is official language
    'ZA': 'af',   # South Africa — Afrikaans widely spoken
    'UG': 'en', 'TZ': 'en', 'ET': 'en',
    'RW': 'en', 'NG': 'en', 'GH': 'en',
}

SUPPORTED_LANGUAGES = ['en', 'af', 'ng']

LANGUAGE_DISPLAY_NAMES: Dict[str, str] = {
    'en': 'English', 'af': 'Afrikaans', 'ng': 'Oshiwambo',
    'naq': 'Damara/Nama', 'hz': 'Herero', 'kav': 'Kavango',
}


# ── Service ────────────────────────────────────────────────────────────────────

class TranslationService:
    """Multi-language translation for health communications."""

    def __init__(self):
        self.default_language: str = getattr(settings, 'LANGUAGE_CODE', 'en')[:2]
        if self.default_language not in SUPPORTED_LANGUAGES:
            self.default_language = 'en'
        # Mutable copy allows runtime additions
        self._terms: Dict[str, Dict[str, str]] = {
            lang: dict(terms) for lang, terms in HEALTH_TERMS.items()
        }

    # ── Term translation ───────────────────────────────────────────────────────

    def translate_term(self, term: str, target_language: str = 'en') -> str:
        """
        Translate a single health term. Falls back to the original term if
        the target language or the term is unknown.
        """
        lang = target_language if target_language in SUPPORTED_LANGUAGES else self.default_language
        term_lower = term.lower()
        translated = self._terms.get(lang, {}).get(term_lower, term)
        return translated.capitalize() if term[:1].isupper() else translated

    def add_translation(self, term: str, translations: Dict[str, str]) -> None:
        """Register a custom term translation at runtime."""
        for lang, value in translations.items():
            if lang in SUPPORTED_LANGUAGES:
                self._terms.setdefault(lang, {})[term.lower()] = value
                logger.info("Registered translation for '%s' in %s", term, lang)

    # ── Template-based messages ────────────────────────────────────────────────

    def translate_message(
        self, template_name: str, target_language: str, **kwargs
    ) -> str:
        """
        Fill a predefined message template in the requested language.
        Falls back to English if the language or template is absent.
        """
        lang = target_language if target_language in SUPPORTED_LANGUAGES else self.default_language
        templates = MESSAGE_TEMPLATES.get(template_name, {})
        template = templates.get(lang) or templates.get('en', '')
        if not template:
            logger.error("Message template '%s' not found", template_name)
            return ''
        try:
            return template.format(**kwargs)
        except KeyError as exc:
            logger.error("Missing variable %s in template '%s'", exc, template_name)
            return template

    # ── Custom message translation ─────────────────────────────────────────────

    def translate_custom_message(self, message: str, target_language: str) -> str:
        """
        Translate a free-form message using Django's i18n system.
        For unlocalised strings, attempts word-level term substitution.
        """
        from django.utils import translation

        if target_language not in SUPPORTED_LANGUAGES:
            return message

        with translation.override(target_language):
            translated = _(message)
            if translated == message:
                words = message.split()
                translated = ' '.join(
                    self.translate_term(w.strip('.,!?;:'), target_language)
                    for w in words
                )
        return translated

    # ── Per-user helpers ───────────────────────────────────────────────────────

    def detect_user_language(self, user) -> str:
        """Resolve preferred language for a user object."""
        if getattr(user, 'preferred_language', None) in SUPPORTED_LANGUAGES:
            return user.preferred_language
        location = getattr(user, 'location', None)
        if location:
            country_code = getattr(location, 'country_code', '')
            if country_code in COUNTRY_LANGUAGE_MAP:
                return COUNTRY_LANGUAGE_MAP[country_code]
        return self.default_language

    def translate_for_user(
        self,
        user,
        message: str = '',
        template_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Translate for a specific user using their detected language."""
        lang = self.detect_user_language(user)
        if template_name:
            return self.translate_message(template_name, lang, **kwargs)
        return self.translate_custom_message(message, lang)

    # ── DB template rendering ──────────────────────────────────────────────────

    def get_localized_template(
        self, template_id: str, language: str, context: Dict
    ) -> Dict[str, str]:
        """
        Fetch a MessageTemplate from the database and render it with context.
        Falls back to English if the requested language is unavailable.
        """
        from communications.models import MessageTemplate

        lang = language if language in SUPPORTED_LANGUAGES else self.default_language

        def _fetch(lang_code: str) -> Optional['MessageTemplate']:
            return MessageTemplate.objects.filter(
                id=template_id, language=lang_code, is_active=True, is_deleted=False
            ).first()

        template = _fetch(lang) or _fetch(self.default_language)
        if not template:
            logger.error("MessageTemplate %s not found in any supported language", template_id)
            return {'subject': '', 'body': ''}
        return template.render(context)

    # ── Utilities ──────────────────────────────────────────────────────────────

    def format_multilingual_message(self, messages: Dict[str, str]) -> str:
        """Combine per-language message variants into a single block."""
        parts = [
            f"[{LANGUAGE_DISPLAY_NAMES.get(lang, lang.upper())}]\n{msg}"
            for lang, msg in messages.items()
        ]
        return '\n\n'.join(parts)

    def translate_health_alert(
        self,
        disease: str,
        location: str,
        case_count: int,
        language: str,
    ) -> str:
        return self.translate_message(
            'health_alert', language,
            disease=disease, location=location, count=case_count,
        )

    def get_supported_languages(self) -> List[Dict[str, str]]:
        return [
            {'code': code, 'name': LANGUAGE_DISPLAY_NAMES[code]}
            for code in SUPPORTED_LANGUAGES
        ]


# Singleton instance
translation_service = TranslationService()
