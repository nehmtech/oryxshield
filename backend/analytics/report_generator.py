"""
OryxShield - Report Generator
======================================

Three production-ready report generation functions.

Functions:
    generate_who_sitrep    – WHO Situation Report
    generate_ihr_report    – IHR Report
    generate_custom_report – Custom template report
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_who_sitrep(template):
    """
    Generate a WHO Situation Report from a ReportTemplate.

    Args:
        template (ReportTemplate): Active WHO_SITREP template.

    Returns:
        dict: Report payload with title, date, template_id, sections.
    """
    logger.info("Generating WHO SitRep from template: %s", template.name)

    sections = []
    for section in (template.sections or []):
        sections.append({
            'title':   section.get('title', ''),
            'type':    section.get('type', 'text'),
            'content': section.get('content', ''),
            'order':   section.get('order', 0),
        })

    return {
        'title':       'WHO Situation Report',
        'report_type': 'WHO_SITREP',
        'date':        datetime.now().isoformat(),
        'template_id': str(template.id),
        'template_name': template.name,
        'sections':    sections,
        'output_format': template.output_format,
    }


def generate_ihr_report(template):
    """
    Generate an IHR (International Health Regulations) Report.

    Args:
        template (ReportTemplate): Active IHR template.

    Returns:
        dict: Report payload.
    """
    logger.info("Generating IHR Report from template: %s", template.name)

    sections = []
    for section in (template.sections or []):
        sections.append({
            'title':   section.get('title', ''),
            'type':    section.get('type', 'text'),
            'content': section.get('content', ''),
            'order':   section.get('order', 0),
        })

    return {
        'title':         'IHR Report',
        'report_type':   'IHR',
        'date':          datetime.now().isoformat(),
        'template_id':   str(template.id),
        'template_name': template.name,
        'sections':      sections,
        'output_format': template.output_format,
    }


def generate_custom_report(template, data):
    """
    Generate a custom report from a ReportTemplate with injected data.

    Args:
        template (ReportTemplate): The source template.
        data (dict):               Contextual data to embed in the report.

    Returns:
        dict: Report payload including injected data.
    """
    logger.info("Generating custom report from template: %s", template.name)

    sections = []
    for section in (template.sections or []):
        sections.append({
            'title':   section.get('title', ''),
            'type':    section.get('type', 'text'),
            'content': section.get('content', ''),
            'order':   section.get('order', 0),
        })

    return {
        'title':         template.name,
        'report_type':   template.template_type,
        'date':          datetime.now().isoformat(),
        'template_id':   str(template.id),
        'template_name': template.name,
        'sections':      sections,
        'data':          data,
        'output_format': template.output_format,
    }