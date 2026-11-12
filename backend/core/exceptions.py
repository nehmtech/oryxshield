"""
OryxShield - Custom Exceptions
=======================================

Production-ready exception classes and handlers.

Exceptions:
- Base exception class
- HTTP-related exceptions
- Business logic exceptions
- Custom exception handler for DRF
"""

from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.
    
    Features:
    - Consistent error response format
    - Additional debugging information
    - Error logging
    - Request context in errors
    
    Args:
        exc: Exception instance
        context: Exception context
        
    Returns:
        Response: Formatted error response
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Get request from context
        request = context.get('request')
        
        # Customize the response format
        custom_response_data = {
            'error': {
                'status_code': response.status_code,
                'message': str(exc),
                'details': response.data,
                'type': exc.__class__.__name__,
            }
        }
        
        # Add request information if available
        if request:
            custom_response_data['error']['path'] = request.path
            custom_response_data['error']['method'] = request.method
        
        # Add timestamp
        from django.utils import timezone
        custom_response_data['timestamp'] = timezone.now().isoformat()
        
        # Log error
        if response.status_code >= 500:
            logger.error(
                f"Server Error: {exc.__class__.__name__} - {str(exc)}",
                exc_info=True,
                extra={
                    'request': request,
                    'status_code': response.status_code,
                }
            )
        elif response.status_code >= 400:
            logger.warning(
                f"Client Error: {exc.__class__.__name__} - {str(exc)}",
                extra={
                    'request': request,
                    'status_code': response.status_code,
                }
            )
        
        response.data = custom_response_data
    
    return response


# Base Exception Classes

class OryxShieldAPIException(APIException):
    """
    Base exception class for OryxShield.
    
    All custom exceptions should inherit from this.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('A server error occurred.')
    default_code = 'error'


# Client Error Exceptions (4xx)

class ValidationError(OryxShieldAPIException):
    """Exception for validation errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Invalid input.')
    default_code = 'validation_error'


class AuthenticationError(OryxShieldAPIException):
    """Exception for authentication errors."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Authentication failed.')
    default_code = 'authentication_error'


class PermissionDeniedError(OryxShieldAPIException):
    """Exception for permission denied errors."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You do not have permission to perform this action.')
    default_code = 'permission_denied'


class NotFoundError(OryxShieldAPIException):
    """Exception for resource not found errors."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Resource not found.')
    default_code = 'not_found'


class ConflictError(OryxShieldAPIException):
    """Exception for conflict errors."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Resource conflict occurred.')
    default_code = 'conflict'


class RateLimitExceededError(OryxShieldAPIException):
    """Exception for rate limit exceeded errors."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('Rate limit exceeded. Please try again later.')
    default_code = 'rate_limit_exceeded'


class AccountLockedError(OryxShieldAPIException):
    """Exception for locked account errors."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Account is locked due to multiple failed login attempts.')
    default_code = 'account_locked'


class InvalidCredentialsError(OryxShieldAPIException):
    """Exception for invalid credentials."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Invalid username or password.')
    default_code = 'invalid_credentials'


class TokenExpiredError(OryxShieldAPIException):
    """Exception for expired tokens."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Token has expired.')
    default_code = 'token_expired'


class InvalidTokenError(OryxShieldAPIException):
    """Exception for invalid tokens."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Invalid token.')
    default_code = 'invalid_token'


# Server Error Exceptions (5xx)

class InternalServerError(OryxShieldAPIException):
    """Exception for internal server errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Internal server error occurred.')
    default_code = 'internal_server_error'


class ExternalServiceError(OryxShieldAPIException):
    """Exception for external service errors."""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = _('External service error occurred.')
    default_code = 'external_service_error'


class ServiceUnavailableError(OryxShieldAPIException):
    """Exception for service unavailable errors."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = _('Service temporarily unavailable.')
    default_code = 'service_unavailable'


# Business Logic Exceptions

class DataProcessingError(OryxShieldAPIException):
    """Exception for data processing errors."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _('Data processing error occurred.')
    default_code = 'data_processing_error'


class ConfigurationError(OryxShieldAPIException):
    """Exception for configuration errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('System configuration error.')
    default_code = 'configuration_error'


class DatabaseError(OryxShieldAPIException):
    """Exception for database errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Database error occurred.')
    default_code = 'database_error'


class CacheError(OryxShieldAPIException):
    """Exception for cache errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Cache error occurred.')
    default_code = 'cache_error'


class FileUploadError(OryxShieldAPIException):
    """Exception for file upload errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('File upload error occurred.')
    default_code = 'file_upload_error'


class IntegrationError(OryxShieldAPIException):
    """Exception for integration errors."""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = _('Integration error occurred.')
    default_code = 'integration_error'


# Domain-Specific Exceptions

class SurveillanceDataError(OryxShieldAPIException):
    """Exception for surveillance data errors."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _('Surveillance data error occurred.')
    default_code = 'surveillance_data_error'


class RiskAssessmentError(OryxShieldAPIException):
    """Exception for risk assessment errors."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _('Risk assessment error occurred.')
    default_code = 'risk_assessment_error'


class ResponseEscalationError(OryxShieldAPIException):
    """Exception for response escalation errors."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _('Response escalation error occurred.')
    default_code = 'response_escalation_error'


class NotificationError(OryxShieldAPIException):
    """Exception for notification errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Notification error occurred.')
    default_code = 'notification_error'


class MLModelError(OryxShieldAPIException):
    """Exception for machine learning model errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Machine learning model error occurred.')
    default_code = 'ml_model_error'


class GeospatialError(OryxShieldAPIException):
    """Exception for geospatial data errors."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _('Geospatial data error occurred.')
    default_code = 'geospatial_error'


class LocationHierarchyError(OryxShieldAPIException):
    """Exception for location hierarchy errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Location hierarchy error occurred.')
    default_code = 'location_hierarchy_error'


class APIKeyError(OryxShieldAPIException):
    """Exception for API key errors."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Invalid or expired API key.')
    default_code = 'api_key_error'


class TwoFactorAuthError(OryxShieldAPIException):
    """Exception for two-factor authentication errors."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Two-factor authentication failed.')
    default_code = 'two_factor_auth_error'


class SocialAuthError(OryxShieldAPIException):
    """Exception for social authentication errors."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Social authentication failed.')
    default_code = 'social_auth_error'


class EmailVerificationError(OryxShieldAPIException):
    """Exception for email verification errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Email verification failed.')
    default_code = 'email_verification_error'


class PasswordResetError(OryxShieldAPIException):
    """Exception for password reset errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Password reset failed.')
    default_code = 'password_reset_error'


# Audit and Compliance Exceptions

class AuditLogError(OryxShieldAPIException):
    """Exception for audit log errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Audit log error occurred.')
    default_code = 'audit_log_error'


class ComplianceError(OryxShieldAPIException):
    """Exception for compliance errors."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Compliance requirement not met.')
    default_code = 'compliance_error'


class DataRetentionError(OryxShieldAPIException):
    """Exception for data retention errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _('Data retention policy error.')
    default_code = 'data_retention_error'


# Utility Functions

def raise_validation_error(message: str, field: str = None):
    """
    Raise validation error with optional field specification.
    
    Args:
        message: Error message
        field: Field name (optional)
        
    Raises:
        ValidationError
    """
    if field:
        raise ValidationError({field: message})
    raise ValidationError(message)


def raise_not_found(resource: str, identifier: str = None):
    """
    Raise not found error for specific resource.
    
    Args:
        resource: Resource name
        identifier: Resource identifier (optional)
        
    Raises:
        NotFoundError
    """
    if identifier:
        raise NotFoundError(_(f'{resource} with identifier "{identifier}" not found.'))
    raise NotFoundError(_(f'{resource} not found.'))


def raise_permission_denied(action: str = None):
    """
    Raise permission denied error with optional action.
    
    Args:
        action: Action that was denied (optional)
        
    Raises:
        PermissionDeniedError
    """
    if action:
        raise PermissionDeniedError(
            _(f'You do not have permission to {action}.')
        )
    raise PermissionDeniedError()


def handle_exception_gracefully(func):
    """
    Decorator to handle exceptions gracefully and log them.
    
    Usage:
        @handle_exception_gracefully
        def my_function():
            # code that might raise exceptions
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OryxShieldAPIException:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Log unexpected exceptions
            logger.error(
                f"Unexpected error in {func.__name__}: {str(e)}",
                exc_info=True
            )
            # Raise as internal server error
            raise InternalServerError(
                _(f'An unexpected error occurred: {str(e)}')
            )
    
    return wrapper