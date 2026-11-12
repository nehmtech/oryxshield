"""
ViewSets for communications app.
All querysets filter is_deleted=False. Mutations use update_fields.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.pagination import CustomPagination
from .models import (
    Broadcast, Campaign, ContactList, FeedbackResponse,
    Message, MessageTemplate, PublicAnnouncement,
    SocialMediaPost,
)
from .serializers import (
    BroadcastEstimateSerializer, BroadcastListSerializer, BroadcastSerializer,
    CampaignListSerializer, CampaignSerializer, CommunicationDashboardSerializer,
    ContactListSerializer, FeedbackAssignSerializer, FeedbackRespondSerializer,
    FeedbackResponseListSerializer, FeedbackResponseSerializer,
    MessageListSerializer, MessageSerializer, MessageTemplateListSerializer,
    MessageTemplateSerializer, PublicAnnouncementListSerializer,
    PublicAnnouncementSerializer, SendBulkMessageSerializer, SendMessageSerializer,
    SocialMediaPostSerializer,
)

User = get_user_model()


# ── MessageTemplate ────────────────────────────────────────────────────────────

class MessageTemplateViewSet(viewsets.ModelViewSet):
    queryset = MessageTemplate.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['template_type', 'is_active', 'language']
    search_fields = ['name', 'subject', 'body']
    ordering_fields = ['created_at', 'name', 'template_type']
    ordering = ['-created_at']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return MessageTemplateListSerializer if self.action == 'list' else MessageTemplateSerializer

    @action(detail=False, methods=['get'])
    def by_language(self, request):
        """List active templates for a specific language."""
        lang = request.query_params.get('language', 'en')
        qs = self.get_queryset().filter(language=lang, is_active=True)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Create a copy of this template."""
        src = self.get_object()
        copy = MessageTemplate.objects.create(
            name=f"{src.name} (Copy)",
            template_type=src.template_type,
            language=src.language,
            subject=src.subject,
            body=src.body,
            variables=src.variables,
        )
        return Response(MessageTemplateSerializer(copy).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def render_preview(self, request, pk=None):
        """Render template with supplied context variables."""
        template = self.get_object()
        context = request.data.get('context', {})
        return Response(template.render(context))


# ── Campaign ───────────────────────────────────────────────────────────────────

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.filter(is_deleted=False).select_related('campaign_manager')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign_type', 'status', 'campaign_manager']
    search_fields = ['name', 'description']
    ordering_fields = ['start_date', 'end_date', 'created_at', 'actual_reach']
    ordering = ['-start_date']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return CampaignListSerializer if self.action == 'list' else CampaignSerializer

    def perform_create(self, serializer):
        serializer.save(campaign_manager=self.request.user)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Campaigns currently running."""
        now = timezone.now()
        qs = self.get_queryset().filter(status='ACTIVE', start_date__lte=now, end_date__gte=now)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        campaign = self.get_object()
        msgs = Message.objects.filter(campaign=campaign, is_deleted=False)
        sent = msgs.filter(status__in=['SENT', 'DELIVERED']).count()
        delivered = msgs.filter(status='DELIVERED').count()
        return Response({
            'total_messages': msgs.count(),
            'messages_sent': sent,
            'messages_delivered': delivered,
            'messages_failed': msgs.filter(status='FAILED').count(),
            'delivery_rate': round(delivered / sent * 100, 2) if sent else 0,
            'channel_breakdown': dict(
                msgs.values('channel').annotate(c=Count('id')).values_list('channel', 'c')
            ),
            'actual_reach': campaign.actual_reach,
            'target_reach': campaign.target_reach,
            'reach_percentage': campaign.reach_percentage,
            'budget': float(campaign.budget),
            'spent': float(campaign.spent),
        })

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = 'ACTIVE'
        campaign.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'Campaign activated'})

    @action(detail=True, methods=['post'])
    def launch(self, request, pk=None):
        """Alias for activate — launch a draft or paused campaign."""
        campaign = self.get_object()
        if campaign.status == 'ACTIVE':
            return Response({'detail': 'Campaign is already active.'}, status=status.HTTP_400_BAD_REQUEST)
        campaign.status = 'ACTIVE'
        campaign.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = 'PAUSED'
        campaign.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'Campaign paused'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = 'COMPLETED'
        campaign.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'Campaign marked as completed'})

    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """Return delivery and reach metrics for the campaign."""
        campaign = self.get_object()
        messages_qs = campaign.messages.all() if hasattr(campaign, 'messages') else Message.objects.filter(campaign=campaign)
        total = messages_qs.count()
        sent = messages_qs.filter(status='SENT').count()
        delivered = messages_qs.filter(status='DELIVERED').count()
        failed = messages_qs.filter(status='FAILED').count()
        reach_pct = round((campaign.actual_reach / campaign.target_reach * 100), 1) if campaign.target_reach else 0
        budget_utilisation = round((float(campaign.spent) / float(campaign.budget) * 100), 1) if campaign.budget else 0
        return Response({
            'campaign_id': campaign.pk,
            'campaign_name': campaign.name,
            'status': campaign.status,
            'target_reach': campaign.target_reach,
            'actual_reach': campaign.actual_reach,
            'reach_percentage': reach_pct,
            'budget': float(campaign.budget),
            'spent': float(campaign.spent),
            'budget_utilisation_percentage': budget_utilisation,
            'messages': {
                'total': total,
                'sent': sent,
                'delivered': delivered,
                'failed': failed,
                'delivery_rate': round(delivered / total * 100, 1) if total else 0,
            },
        })


# ── Message ────────────────────────────────────────────────────────────────────

class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.filter(is_deleted=False).select_related('campaign', 'template')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['channel', 'status', 'priority', 'campaign']
    search_fields = ['recipient_identifier', 'subject', 'body']
    ordering_fields = ['created_at', 'sent_at', 'delivered_at', 'priority']
    ordering = ['-created_at']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return MessageListSerializer if self.action == 'list' else MessageSerializer

    @action(detail=False, methods=['post'])
    def send(self, request):
        """Enqueue a single message for delivery."""
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        from .tasks import send_message
        task = send_message.delay(
            d['channel'], d['recipient'],
            d.get('subject', ''), d['body'],
            d.get('priority', 'NORMAL'),
            str(d['campaign_id']) if d.get('campaign_id') else None,
        )
        return Response(
            {'status': 'Message queued', 'task_id': str(task.id)},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=['post'])
    def send_bulk(self, request):
        """Enqueue bulk messages."""
        ser = SendBulkMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        from .tasks import send_bulk_messages
        task = send_bulk_messages.delay(ser.validated_data)
        return Response(
            {
                'status': 'Bulk messages queued',
                'task_id': str(task.id),
                'recipient_count': len(ser.validated_data['recipients']),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=['get'])
    def pending(self, request):
        qs = self.get_queryset().filter(status__in=['PENDING', 'QUEUED'])
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=['get'])
    def failed(self, request):
        qs = self.get_queryset().filter(status='FAILED')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        message = self.get_object()
        if not message.can_retry():
            return Response(
                {'error': 'Message has reached maximum retry limit'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .tasks import send_message
        message.status = 'QUEUED'
        message.retry_count += 1
        message.save(update_fields=['status', 'retry_count', 'updated_at'])
        task = send_message.delay(
            message.channel, message.recipient_identifier,
            message.subject, message.body, message.priority,
        )
        return Response({'status': 'Message queued for retry', 'task_id': str(task.id)})


# ── Broadcast ──────────────────────────────────────────────────────────────────

class BroadcastViewSet(viewsets.ModelViewSet):
    queryset = Broadcast.objects.filter(is_deleted=False).select_related('campaign', 'created_by', 'approved_by')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'campaign']
    ordering_fields = ['created_at', 'scheduled_for', 'total_recipients']
    ordering = ['-created_at']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return BroadcastListSerializer if self.action == 'list' else BroadcastSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        broadcast = self.get_object()
        if broadcast.status != 'DRAFT':
            return Response({'error': 'Only DRAFT broadcasts can be submitted'}, status=status.HTTP_400_BAD_REQUEST)
        broadcast.status = 'PENDING_APPROVAL'
        broadcast.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'Broadcast submitted for approval'})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        broadcast = self.get_object()
        if broadcast.status not in ['DRAFT', 'PENDING_APPROVAL']:
            return Response({'error': 'Broadcast is not in an approvable state'}, status=status.HTTP_400_BAD_REQUEST)
        broadcast.approve(request.user)
        return Response({'status': 'Broadcast approved'})

    @action(detail=True, methods=['post'])
    def send_now(self, request, pk=None):
        broadcast = self.get_object()
        if broadcast.status not in ['APPROVED', 'SCHEDULED']:
            return Response({'error': 'Broadcast must be approved before sending'}, status=status.HTTP_400_BAD_REQUEST)
        from .tasks import process_broadcast
        task = process_broadcast.delay(str(broadcast.id))
        return Response({'status': 'Broadcast sending', 'task_id': str(task.id)})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        broadcast = self.get_object()
        if broadcast.status in ['SENT', 'SENDING']:
            return Response({'error': 'Cannot cancel a broadcast that is already sending or sent'}, status=status.HTTP_400_BAD_REQUEST)
        broadcast.cancel()
        return Response({'status': 'Broadcast cancelled'})

    @action(detail=False, methods=['post'])
    def estimate_reach(self, request):
        """Estimate recipient count for a targeting configuration."""
        ser = BroadcastEstimateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        from .geo_targeting import geo_targeting
        d = ser.validated_data
        estimated = geo_targeting.estimate_reach(
            target_locations=[str(lid) for lid in d['location_ids']],
            target_criteria=d.get('criteria', {}),
            include_sublocations=d.get('include_sublocations', True),
        )
        return Response({'estimated_reach': estimated, 'location_count': len(d['location_ids'])})


# ── ContactList ────────────────────────────────────────────────────────────────

class ContactListViewSet(viewsets.ModelViewSet):
    queryset = ContactList.objects.filter(is_deleted=False)
    serializer_class = ContactListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'location']
    search_fields = ['name', 'description', 'tags']
    pagination_class = CustomPagination

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(owner=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def add_contacts(self, request, pk=None):
        contact_list = self.get_object()
        new_contacts = request.data.get('contacts', [])
        if not isinstance(new_contacts, list):
            return Response({'error': 'contacts must be a list'}, status=status.HTTP_400_BAD_REQUEST)
        total = contact_list.add_contacts(new_contacts)
        return Response({'status': 'Contacts added', 'total_contacts': total})

    @action(detail=True, methods=['post'])
    def remove_contacts(self, request, pk=None):
        contact_list = self.get_object()
        identifiers = request.data.get('identifiers', [])
        if not isinstance(identifiers, list):
            return Response({'error': 'identifiers must be a list'}, status=status.HTTP_400_BAD_REQUEST)
        total = contact_list.remove_contacts(identifiers)
        return Response({'status': 'Contacts removed', 'total_contacts': total})


# ── PublicAnnouncement ─────────────────────────────────────────────────────────

class PublicAnnouncementViewSet(viewsets.ModelViewSet):
    queryset = PublicAnnouncement.objects.filter(is_deleted=False).select_related('author')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['announcement_type', 'is_published', 'is_featured']
    search_fields = ['title', 'content', 'summary', 'tags']
    ordering_fields = ['display_priority', 'publish_date', 'created_at', 'view_count']
    ordering = ['-display_priority', '-publish_date']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return PublicAnnouncementListSerializer if self.action == 'list' else PublicAnnouncementSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=False, methods=['get'])
    def published(self, request):
        qs = self.get_queryset().filter(is_published=True)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        qs = self.get_queryset().filter(is_published=True, is_featured=True)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        announcement = self.get_object()
        announcement.publish()
        return Response({'status': 'Announcement published', 'publish_date': announcement.publish_date})

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        announcement = self.get_object()
        announcement.unpublish()
        return Response({'status': 'Announcement unpublished'})

    @action(detail=True, methods=['post'])
    def track_view(self, request, pk=None):
        """Increment view counter atomically."""
        announcement = self.get_object()
        count = announcement.increment_view()
        return Response({'view_count': count})


# ── SocialMediaPost ────────────────────────────────────────────────────────────

class SocialMediaPostViewSet(viewsets.ModelViewSet):
    queryset = SocialMediaPost.objects.filter(is_deleted=False).select_related('campaign', 'created_by')
    serializer_class = SocialMediaPostSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['platform', 'status', 'campaign']
    ordering_fields = ['published_at', 'created_at', 'reach', 'impressions']
    ordering = ['-published_at']
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def publish_now(self, request, pk=None):
        """Publish post to platform immediately."""
        post = self.get_object()
        if post.status == 'PUBLISHED':
            return Response({'error': 'Post is already published'}, status=status.HTTP_400_BAD_REQUEST)
        from .social_media import social_media_service
        result = social_media_service.post_to_platform(
            platform=post.platform,
            content=post.content,
            media_urls=post.media_urls,
            hashtags=post.hashtags,
        )
        if result['success']:
            post.mark_published(result['post_id'], result['post_url'])
            return Response({'status': 'Post published', 'post_url': result['post_url']})
        return Response({'error': result.get('error', 'Publishing failed')}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def refresh_metrics(self, request, pk=None):
        """Fetch latest engagement metrics from platform."""
        post = self.get_object()
        if not post.platform_post_id:
            return Response({'error': 'No platform post ID — post has not been published'}, status=status.HTTP_400_BAD_REQUEST)
        from .social_media import social_media_service
        metrics = social_media_service.update_post_metrics(post.platform_post_id, post.platform)
        if metrics:
            post.update_metrics(metrics)
            return Response(SocialMediaPostSerializer(post).data)
        return Response({'error': 'Could not retrieve metrics'}, status=status.HTTP_400_BAD_REQUEST)


# ── FeedbackResponse ───────────────────────────────────────────────────────────

class FeedbackResponseViewSet(viewsets.ModelViewSet):
    queryset = FeedbackResponse.objects.filter(is_deleted=False).select_related('assigned_to')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['feedback_type', 'status', 'is_urgent', 'assigned_to']
    search_fields = ['sender_name', 'subject', 'message']
    ordering_fields = ['created_at', 'is_urgent']
    ordering = ['-is_urgent', '-created_at']
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return FeedbackResponseListSerializer if self.action == 'list' else FeedbackResponseSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        qs = self.get_queryset().filter(status__in=['RECEIVED', 'UNDER_REVIEW'])
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=False, methods=['get'])
    def urgent(self, request):
        qs = self.get_queryset().filter(is_urgent=True, status__in=['RECEIVED', 'UNDER_REVIEW'])
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        ser = FeedbackAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        feedback = self.get_object()
        try:
            assignee = User.objects.get(id=ser.validated_data['assigned_to'], is_active=True)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        feedback.assign(assignee)
        return Response({'status': 'Feedback assigned', 'assigned_to': str(assignee.id)})

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        ser = FeedbackRespondSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        feedback = self.get_object()
        feedback.respond(ser.validated_data['response'])
        if feedback.sender_email:
            from .tasks import send_email_notification
            from .email_service import email_service
            email_service.send_feedback_response(
                to_email=feedback.sender_email,
                sender_name=feedback.sender_name,
                original_subject=feedback.subject,
                response_text=ser.validated_data['response'],
            )
        return Response({'status': 'Response sent', 'responded_at': feedback.responded_at})

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        feedback = self.get_object()
        feedback.resolve()
        return Response({'status': 'Feedback resolved', 'resolved_at': feedback.resolved_at})

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        feedback = self.get_object()
        notes = request.data.get('notes', '')
        feedback.escalate(notes)
        return Response({'status': 'Feedback escalated'})


# ── Dashboard ──────────────────────────────────────────────────────────────────

class CommunicationDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Aggregate dashboard statistics for the communications system."""
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)

        active_campaigns = Campaign.objects.filter(
            status='ACTIVE', start_date__lte=now, end_date__gte=now, is_deleted=False
        ).count()

        messages_today = Message.objects.filter(
            sent_at__date=today, is_deleted=False
        ).count()

        messages_pending = Message.objects.filter(
            status__in=['PENDING', 'QUEUED'], is_deleted=False
        ).count()

        recent_msgs = Message.objects.filter(created_at__gte=week_ago, is_deleted=False)
        total_sent = recent_msgs.filter(status__in=['SENT', 'DELIVERED']).count()
        delivered = recent_msgs.filter(status='DELIVERED').count()
        delivery_rate_7d = round(delivered / total_sent * 100, 2) if total_sent else 0

        recent_broadcasts = list(
            Broadcast.objects.filter(is_deleted=False)
            .order_by('-created_at')[:5]
            .values('id', 'title', 'status', 'messages_sent', 'messages_delivered', 'created_at')
        )

        channel_usage = dict(
            Message.objects.filter(is_deleted=False)
            .values('channel')
            .annotate(count=Count('id'))
            .values_list('channel', 'count')
        )

        feedback_pending = FeedbackResponse.objects.filter(
            status__in=['RECEIVED', 'UNDER_REVIEW'], is_deleted=False
        ).count()

        announcements_live = PublicAnnouncement.objects.filter(
            is_published=True, is_deleted=False
        ).count()

        data = {
            'active_campaigns': active_campaigns,
            'messages_sent_today': messages_today,
            'messages_pending': messages_pending,
            'delivery_rate_7d': delivery_rate_7d,
            'recent_broadcasts': recent_broadcasts,
            'channel_usage': channel_usage,
            'feedback_pending': feedback_pending,
            'announcements_live': announcements_live,
        }
        return Response(CommunicationDashboardSerializer(data).data)