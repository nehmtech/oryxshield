"""
OryxShield - Data Export Formats
=========================================

Three production-ready export functions.

Functions:
    export_to_csv   – write list[dict] to CSV string
    export_to_json  – write list[dict] to JSON string
    export_to_excel – write list[dict] to Excel bytes (XLSX)
"""

import csv
import json
import io
import logging

logger = logging.getLogger(__name__)


def export_to_csv(data):
    """
    Export data to CSV format.

    Args:
        data (list[dict]): Rows to serialise; all dicts must share the same keys.

    Returns:
        str: CSV content (UTF-8 string).

    Raises:
        ValueError: If data is empty.
    """
    if not data:
        raise ValueError("Cannot export empty dataset to CSV")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
    writer.writeheader()
    writer.writerows(data)

    logger.info("Exported %d rows to CSV", len(data))
    return output.getvalue()


def export_to_json(data, indent=2):
    """
    Export data to JSON format.

    Args:
        data (list[dict]): Serialisable records.
        indent (int):      JSON indentation level (default 2).

    Returns:
        str: JSON-encoded string.
    """
    content = json.dumps(data, indent=indent, default=str)
    logger.info("Exported %d records to JSON", len(data) if isinstance(data, list) else 1)
    return content


def export_to_excel(data):
    """
    Export data to Excel XLSX format.

    Requires openpyxl.

    Args:
        data (list[dict]): Rows to write; all dicts must share the same keys.

    Returns:
        bytes: Raw XLSX file content.

    Raises:
        ImportError: If openpyxl is not installed.
        ValueError:  If data is empty.
    """
    if not data:
        raise ValueError("Cannot export empty dataset to Excel")

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise ImportError("openpyxl is required for Excel export: pip install openpyxl")

    wb     = openpyxl.Workbook()
    ws     = wb.active
    ws.title = 'Export'

    headers    = list(data[0].keys())
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')

    for col_idx, header in enumerate(headers, start=1):
        cell              = ws.cell(row=1, column=col_idx, value=header)
        cell.font         = header_font
        cell.fill         = header_fill
        cell.alignment    = Alignment(horizontal='center')

    for row_idx, record in enumerate(data, start=2):
        for col_idx, header in enumerate(headers, start=1):
            ws.cell(row=row_idx, column=col_idx, value=record.get(header))

    # Auto-size columns (capped at 50 chars)
    for col in ws.columns:
        max_len = max((len(str(cell.value or '')) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 52)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    logger.info("Exported %d rows to Excel", len(data))
    return output.getvalue()