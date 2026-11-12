"""
Social media service for OryxShield communications.
Supports Twitter/X and Facebook with local mock fallback for all other platforms.
"""
import logging
import uuid
import random
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class SocialMediaProvider:
    """Base class for social media providers."""

    def post(
        self,
        content: str,
        media_urls: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
    ) -> Dict:
        raise NotImplementedError

    def get_post_metrics(self, post_id: str) -> Dict:
        raise NotImplementedError


# ── Twitter / X ────────────────────────────────────────────────────────────────

class TwitterProvider(SocialMediaProvider):

    def __init__(self):
        self.bearer_token = getattr(settings, 'TWITTER_BEARER_TOKEN', '')
        self.api_url = 'https://api.twitter.com/2'

    def post(
        self,
        content: str,
        media_urls: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
    ) -> Dict:
        if not self.bearer_token:
            return {'success': False, 'post_id': '', 'post_url': '', 'error': 'Twitter credentials not configured'}
        try:
            text = content
            if hashtags:
                text += '\n\n' + ' '.join(f'#{tag}' for tag in hashtags)
            response = requests.post(
                f'{self.api_url}/tweets',
                headers={'Authorization': f'Bearer {self.bearer_token}', 'Content-Type': 'application/json'},
                json={'text': text[:280]},
                timeout=30,
            )
            response.raise_for_status()
            tweet_id = response.json().get('data', {}).get('id', '')
            return {
                'success': True,
                'post_id': tweet_id,
                'post_url': f'https://twitter.com/i/web/status/{tweet_id}',
                'error': '',
            }
        except Exception as exc:
            logger.error("Twitter post error: %s", exc)
            return {'success': False, 'post_id': '', 'post_url': '', 'error': str(exc)}

    def get_post_metrics(self, post_id: str) -> Dict:
        if not self.bearer_token:
            return {}
        try:
            response = requests.get(
                f'{self.api_url}/tweets/{post_id}',
                headers={'Authorization': f'Bearer {self.bearer_token}'},
                params={'tweet.fields': 'public_metrics'},
                timeout=30,
            )
            response.raise_for_status()
            m = response.json().get('data', {}).get('public_metrics', {})
            return {
                'likes': m.get('like_count', 0),
                'shares': m.get('retweet_count', 0),
                'comments': m.get('reply_count', 0),
                'impressions': m.get('impression_count', 0),
                'reach': m.get('impression_count', 0),
            }
        except Exception as exc:
            logger.error("Twitter metrics error: %s", exc)
            return {}


# ── Facebook ───────────────────────────────────────────────────────────────────

class FacebookProvider(SocialMediaProvider):

    def __init__(self):
        self.access_token = getattr(settings, 'FACEBOOK_ACCESS_TOKEN', '')
        self.page_id = getattr(settings, 'FACEBOOK_PAGE_ID', '')
        self.api_url = 'https://graph.facebook.com/v18.0'

    def post(
        self,
        content: str,
        media_urls: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
    ) -> Dict:
        if not self.access_token or not self.page_id:
            return {'success': False, 'post_id': '', 'post_url': '', 'error': 'Facebook credentials not configured'}
        try:
            text = content
            if hashtags:
                text += '\n\n' + ' '.join(f'#{tag}' for tag in hashtags)
            payload = {'message': text, 'access_token': self.access_token}
            if media_urls:
                payload['link'] = media_urls[0]
            response = requests.post(
                f'{self.api_url}/{self.page_id}/feed', data=payload, timeout=30
            )
            response.raise_for_status()
            post_id = response.json().get('id', '')
            return {
                'success': True,
                'post_id': post_id,
                'post_url': f'https://www.facebook.com/{post_id}',
                'error': '',
            }
        except Exception as exc:
            logger.error("Facebook post error: %s", exc)
            return {'success': False, 'post_id': '', 'post_url': '', 'error': str(exc)}

    def get_post_metrics(self, post_id: str) -> Dict:
        if not self.access_token:
            return {}
        try:
            response = requests.get(
                f'{self.api_url}/{post_id}',
                params={
                    'fields': 'shares,likes.summary(true),comments.summary(true)',
                    'access_token': self.access_token,
                },
                timeout=30,
            )
            response.raise_for_status()
            r = response.json()
            return {
                'likes': r.get('likes', {}).get('summary', {}).get('total_count', 0),
                'shares': r.get('shares', {}).get('count', 0),
                'comments': r.get('comments', {}).get('summary', {}).get('total_count', 0),
                'reach': 0,
                'impressions': 0,
            }
        except Exception as exc:
            logger.error("Facebook metrics error: %s", exc)
            return {}


# ── Local mock ─────────────────────────────────────────────────────────────────

class LocalSocialMediaProvider(SocialMediaProvider):
    """Development mock — logs content, returns deterministic IDs."""

    def post(
        self,
        content: str,
        media_urls: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
    ) -> Dict:
        post_id = str(uuid.uuid4())
        logger.info("[LOCAL SOCIAL] content=%s…", content[:80])
        return {'success': True, 'post_id': post_id, 'post_url': f'https://example.com/posts/{post_id}', 'error': ''}

    def get_post_metrics(self, post_id: str) -> Dict:
        return {
            'likes': random.randint(10, 500),
            'shares': random.randint(2, 100),
            'comments': random.randint(0, 50),
            'reach': random.randint(200, 5000),
            'impressions': random.randint(400, 10000),
        }


# ── Service ────────────────────────────────────────────────────────────────────

class SocialMediaService:
    """
    Multi-platform social media service.
    Platform providers resolve from settings; unsupported platforms fall back to mock.
    """

    def __init__(self):
        twitter = TwitterProvider() if getattr(settings, 'TWITTER_BEARER_TOKEN', '') else LocalSocialMediaProvider()
        facebook = FacebookProvider() if getattr(settings, 'FACEBOOK_ACCESS_TOKEN', '') else LocalSocialMediaProvider()
        self.providers: Dict[str, SocialMediaProvider] = {
            'TWITTER': twitter,
            'FACEBOOK': facebook,
            'INSTAGRAM': LocalSocialMediaProvider(),
            'LINKEDIN': LocalSocialMediaProvider(),
            'YOUTUBE': LocalSocialMediaProvider(),
        }

    def post_to_platform(
        self,
        platform: str,
        content: str,
        media_urls: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
    ) -> Dict:
        provider = self.providers.get(platform)
        if not provider:
            return {'success': False, 'post_id': '', 'post_url': '', 'error': f'Unsupported platform: {platform}'}
        result = provider.post(content, media_urls, hashtags)
        if result['success']:
            logger.info("Posted to %s: %s", platform, result['post_id'])
        else:
            logger.error("Post to %s failed: %s", platform, result.get('error'))
        return result

    def post_to_multiple_platforms(
        self,
        platforms: List[str],
        content: str,
        media_urls: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
    ) -> Dict[str, Dict]:
        results = {p: self.post_to_platform(p, content, media_urls, hashtags) for p in platforms}
        success_count = sum(1 for r in results.values() if r['success'])
        logger.info("Posted to %d/%d platforms", success_count, len(platforms))
        return results

    def update_post_metrics(self, post_id: str, platform: str) -> Dict:
        provider = self.providers.get(platform)
        if not provider:
            return {}
        return provider.get_post_metrics(post_id)

    def schedule_post(
        self,
        platform: str,
        content: str,
        scheduled_time: timezone.datetime,
        media_urls: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        campaign_id: Optional[str] = None,
    ) -> Dict:
        """
        Persist a SocialMediaPost record in SCHEDULED status and enqueue the Celery task.
        """
        from communications.models import SocialMediaPost
        from communications.tasks import publish_scheduled_social_post

        post = SocialMediaPost.objects.create(
            platform=platform,
            content=content,
            media_urls=media_urls or [],
            hashtags=hashtags or [],
            status='SCHEDULED',
            scheduled_for=scheduled_time,
            campaign_id=campaign_id,
        )
        publish_scheduled_social_post.apply_async(args=[str(post.id)], eta=scheduled_time)
        logger.info("Scheduled %s post for %s (id=%s)", platform, scheduled_time, post.id)
        return {'success': True, 'post_id': str(post.id), 'scheduled_for': scheduled_time.isoformat()}


# Singleton instance
social_media_service = SocialMediaService()