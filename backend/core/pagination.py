"""
OryxShield - Custom Pagination
=======================================

Production-ready pagination classes.
"""

from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from collections import OrderedDict


class CustomPagination(PageNumberPagination):
    """Custom page number pagination with configurable page size."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000
    page_query_param = 'page'

    def get_paginated_response(self, data):
        """Return paginated response with metadata."""
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

class CustomCursorPagination(CursorPagination):
    """Default cursor-based pagination for the OryxShield API."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500
    ordering = '-created_at'

class LargePagination(PageNumberPagination):
    """Pagination for large datasets."""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 5000


class SmallPagination(PageNumberPagination):
    """Pagination for small datasets or mobile apps."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class TimeBasedPagination(CursorPagination):
    """Cursor-based pagination for time-series data."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000
    ordering = '-created_at'