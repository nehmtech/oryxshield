"""
OryxShield - Reusable Mixins
=====================================

Production-ready mixins for models and views.

Model Mixins:
- SoftDeleteMixin: Soft delete functionality
- AuditMixin: Created/updated by tracking
- LocationMixin: Location foreign key
- MetadataMixin: JSON metadata field
- StatusMixin: Status tracking
- ApprovalMixin: Approval workflow

View Mixins:
- SoftDeleteViewMixin: Soft delete/restore actions
- ApprovalViewMixin: Approve/reject actions
- BulkOperationsMixin: Bulk create/update/delete
- ExportMixin: CSV/JSON export
- StatisticsMixin: Statistics endpoints
- SearchMixin: Advanced search
"""

from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
import logging

logger = logging.getLogger(__name__)


# Model Mixins

class SoftDeleteMixin(models.Model):
    """
    Mixin to add soft delete functionality to models.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self, commit=True):
        """Soft delete the object."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if commit:
            self.save(update_fields=['is_deleted', 'deleted_at'])
        return self

    def restore(self, commit=True):
        """Restore a soft-deleted object."""
        self.is_deleted = False
        self.deleted_at = None
        if commit:
            self.save(update_fields=['is_deleted', 'deleted_at'])
        return self


class AuditMixin(models.Model):
    """
    Mixin to add audit fields to models.
    """
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created'
    )
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated'
    )

    class Meta:
        abstract = True


class LocationMixin(models.Model):
    """
    Mixin to add location fields to models.
    """
    location = models.ForeignKey(
        'core.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_locations'
    )

    class Meta:
        abstract = True


class MetadataMixin(models.Model):
    """
    Mixin to add metadata JSON field to models.
    """
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class StatusMixin(models.Model):
    """
    Mixin to add status tracking to models.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('archived', 'Archived'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )

    class Meta:
        abstract = True


class ApprovalMixin(models.Model):
    """
    Mixin to add approval workflow to models.
    """
    APPROVAL_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='draft',
        db_index=True
    )
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        abstract = True

    def approve(self, user):
        """Approve the object."""
        self.approval_status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()

    def reject(self, user, reason=''):
        """Reject the object."""
        self.approval_status = 'rejected'
        self.approved_by = user
        self.rejection_reason = reason
        self.save()


# View Mixins

class SoftDeleteViewMixin:
    """
    Mixin for viewsets to handle soft delete operations.
    """
    @action(detail=True, methods=['post'])
    def soft_delete(self, request, pk=None):
        """Soft delete an object."""
        obj = self.get_object()
        obj.soft_delete()
        return Response({'status': 'success', 'message': 'Object soft deleted successfully'})

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore a soft-deleted object."""
        obj = self.get_object()
        obj.restore()
        return Response({'status': 'success', 'message': 'Object restored successfully'})


class ApprovalViewMixin:
    """
    Mixin for viewsets to handle approval workflow.
    """
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an object."""
        obj = self.get_object()
        obj.approve(request.user)
        return Response({'status': 'success', 'message': 'Object approved successfully'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an object."""
        obj = self.get_object()
        reason = request.data.get('reason', '')
        obj.reject(request.user, reason)
        return Response({'status': 'success', 'message': 'Object rejected successfully'})


class BulkOperationsMixin:
    """
    Mixin to add bulk operations to viewsets.
    """
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create objects."""
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        """Bulk update objects."""
        ids = request.data.get('ids', [])
        update_data = request.data.get('data', {})
        
        if not ids:
            return Response(
                {'error': 'No IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(id__in=ids)
        count = queryset.update(**update_data)
        
        return Response({
            'status': 'success',
            'message': f'{count} objects updated successfully',
            'count': count
        })

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        """Bulk delete objects."""
        ids = request.data.get('ids', [])
        
        if not ids:
            return Response(
                {'error': 'No IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(id__in=ids)
        count = queryset.count()
        
        # Soft delete if model supports it
        if hasattr(queryset.model, 'soft_delete'):
            for obj in queryset:
                obj.soft_delete()
        else:
            queryset.delete()
        
        return Response({
            'status': 'success',
            'message': f'{count} objects deleted successfully',
            'count': count
        })


class ExportMixin:
    """
    Mixin to add export functionality to viewsets.
    """
    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """Export data as CSV."""
        import csv
        from django.http import HttpResponse
        
        queryset = self.filter_queryset(self.get_queryset())
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.basename}_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        if queryset.exists():
            fields = [f.name for f in queryset.model._meta.fields]
            writer.writerow(fields)
            
            # Write data (limit to prevent memory issues)
            for obj in queryset[:10000]:
                writer.writerow([str(getattr(obj, f, '')) for f in fields])
        
        return response

    @action(detail=False, methods=['get'])
    def export_json(self, request):
        """Export data as JSON."""
        queryset = self.filter_queryset(self.get_queryset())[:10000]
        serializer = self.get_serializer(queryset, many=True)
        
        from django.http import JsonResponse
        return JsonResponse(serializer.data, safe=False)


class StatisticsMixin:
    """
    Mixin to add statistics endpoints to viewsets.
    """
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics for the model."""
        from django.db.models import Count, Avg, Sum, Max, Min
        
        queryset = self.filter_queryset(self.get_queryset())
        
        stats = {
            'total_count': queryset.count(),
        }
        
        # Add soft-delete count if supported
        if hasattr(queryset.model, 'is_deleted'):
            stats['active_count'] = queryset.filter(is_deleted=False).count()
            stats['deleted_count'] = queryset.filter(is_deleted=True).count()
        
        # Add status-based counts if model has status field
        if hasattr(queryset.model, 'status'):
            status_counts = queryset.values('status').annotate(count=Count('id'))
            stats['by_status'] = {item['status']: item['count'] for item in status_counts}
        
        # Add approval status counts if supported
        if hasattr(queryset.model, 'approval_status'):
            approval_counts = queryset.values('approval_status').annotate(count=Count('id'))
            stats['by_approval_status'] = {item['approval_status']: item['count'] for item in approval_counts}
        
        return Response(stats)


class SearchMixin:
    """
    Enhanced search mixin with additional search capabilities.
    """
    @action(detail=False, methods=['get'])
    def advanced_search(self, request):
        """Advanced search with multiple parameters."""
        queryset = self.get_queryset()
        
        # Apply filters from query parameters
        for param, value in request.query_params.items():
            if param not in ['page', 'page_size', 'ordering', 'search']:
                if hasattr(queryset.model, param):
                    queryset = queryset.filter(**{param: value})
        
        # Apply search if provided
        search_query = request.query_params.get('search')
        if search_query and hasattr(self, 'search_fields'):
            from django.db.models import Q
            search_filter = Q()
            for field in self.search_fields:
                search_filter |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(search_filter)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class FilterMixin:
    """
    Mixin to add common filtering capabilities.
    """
    @action(detail=False, methods=['get'])
    def filter_by_date_range(self, request):
        """Filter by date range."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        date_field = request.query_params.get('date_field', 'created_at')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(**{f"{date_field}__gte": start_date})
        if end_date:
            queryset = queryset.filter(**{f"{date_field}__lte": end_date})
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CacheMixin:
    """
    Mixin to add caching to viewset responses.
    """
    cache_timeout = 300  # 5 minutes default
    
    def get_cache_key(self, request):
        """Generate cache key for request."""
        from .utils import cache_key
        return cache_key(
            self.__class__.__name__,
            request.path,
            request.user.id if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
            str(request.query_params)
        )
    
    def list(self, request, *args, **kwargs):
        """List with caching."""
        from django.core.cache import cache
        
        cache_key_str = self.get_cache_key(request)
        cached_response = cache.get(cache_key_str)
        
        if cached_response:
            return Response(cached_response)
        
        response = super().list(request, *args, **kwargs)
        
        if response.status_code == 200:
            cache.set(cache_key_str, response.data, self.cache_timeout)
        
        return response