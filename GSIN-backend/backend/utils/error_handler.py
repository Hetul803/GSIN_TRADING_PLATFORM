# backend/utils/error_handler.py
"""
Centralized error handling utilities.
Provides user-friendly error messages and consistent error responses.
"""
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import traceback
import logging

logger = logging.getLogger(__name__)


class UserFriendlyError(Exception):
    """Exception with user-friendly message."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


def handle_database_error(e: Exception, operation: str = "database operation") -> HTTPException:
    """
    Handle database errors and return user-friendly HTTPException.
    
    Args:
        e: The exception that occurred
        operation: Description of the operation that failed
    
    Returns:
        HTTPException with user-friendly message
    """
    if isinstance(e, IntegrityError):
        # Handle constraint violations (duplicate keys, foreign key violations, etc.)
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            return HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This record already exists. Please check for duplicates."
            )
        elif "foreign key" in error_msg.lower():
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid reference. The related record does not exist."
            )
        else:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database constraint violation. Please check your input."
            )
    
    elif isinstance(e, SQLAlchemyError):
        # Log the full error for debugging
        logger.error(f"Database error during {operation}: {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error occurred. Please try again later."
        )
    
    else:
        # Log unexpected errors
        logger.error(f"Unexpected error during {operation}: {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred. Please try again later."
        )


def handle_validation_error(field: str, reason: str) -> HTTPException:
    """
    Handle validation errors with clear messages.
    
    Args:
        field: Name of the field that failed validation
        reason: Reason for validation failure
    
    Returns:
        HTTPException with validation error message
    """
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Validation error for '{field}': {reason}"
    )


def handle_not_found_error(resource: str, resource_id: Optional[str] = None) -> HTTPException:
    """
    Handle not found errors.
    
    Args:
        resource: Type of resource (e.g., "Strategy", "Trade", "User")
        resource_id: Optional ID of the resource
    
    Returns:
        HTTPException with not found message
    """
    if resource_id:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} with ID '{resource_id}' not found."
        )
    else:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found."
        )


def handle_permission_error(action: str, resource: str) -> HTTPException:
    """
    Handle permission/authorization errors.
    
    Args:
        action: Action that was attempted (e.g., "delete", "modify")
        resource: Type of resource (e.g., "strategy", "group")
    
    Returns:
        HTTPException with permission error message
    """
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You do not have permission to {action} this {resource}."
    )


def handle_market_data_error(e: Exception, symbol: Optional[str] = None) -> HTTPException:
    """
    Handle market data provider errors.
    
    Args:
        e: The exception from market data provider
        symbol: Optional symbol that was being fetched
    
    Returns:
        HTTPException with user-friendly message
    """
    error_msg = str(e).lower()
    
    if "rate limit" in error_msg or "429" in error_msg:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Market data rate limit exceeded. Please try again in a moment."
        )
    elif "not found" in error_msg or "404" in error_msg:
        symbol_text = f" for {symbol}" if symbol else ""
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market data not found{symbol_text}. Please check the symbol and try again."
        )
    elif "authentication" in error_msg or "401" in error_msg or "403" in error_msg:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data service authentication failed. Please contact support."
        )
    else:
        logger.error(f"Market data error: {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data service temporarily unavailable. Please try again later."
        )


def safe_execute(func, *args, default_return=None, error_message: str = "Operation failed", **kwargs):
    """
    Safely execute a function and return default value on error.
    Useful for non-critical operations.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        default_return: Value to return on error
        error_message: Error message to log
        **kwargs: Keyword arguments
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"{error_message}: {e}")
        return default_return

