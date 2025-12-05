# backend/utils/query_batching.py
"""
PHASE 5: Query batching utilities for optimizing database queries.
"""
from typing import List, Dict, Any, Callable, TypeVar, Optional
from sqlalchemy.orm import Session
from functools import wraps
import time

T = TypeVar('T')


def batch_query(
    items: List[Any],
    batch_size: int = 100,
    query_func: Optional[Callable] = None
) -> List[Any]:
    """
    Batch process items to avoid N+1 queries.
    
    Args:
        items: List of items to process
        batch_size: Number of items per batch
        query_func: Optional function to apply to each batch
    
    Returns:
        List of processed items
    """
    if not items:
        return []
    
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        if query_func:
            results.extend(query_func(batch))
        else:
            results.extend(batch)
    
    return results


def batch_load_relationships(
    db: Session,
    items: List[Any],
    relationship_name: str,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Eagerly load relationships for a batch of items to avoid N+1 queries.
    
    Args:
        db: Database session
        items: List of SQLAlchemy model instances
        relationship_name: Name of the relationship to load
        batch_size: Number of items per batch
    
    Returns:
        Dictionary mapping item IDs to loaded relationships
    """
    if not items:
        return {}
    
    # Get IDs
    item_ids = [item.id for item in items if hasattr(item, 'id')]
    if not item_ids:
        return {}
    
    # Load relationships in batches
    results = {}
    for i in range(0, len(item_ids), batch_size):
        batch_ids = item_ids[i:i + batch_size]
        # This is a placeholder - actual implementation depends on the relationship
        # Example: db.query(RelatedModel).filter(RelatedModel.parent_id.in_(batch_ids)).all()
        pass
    
    return results


def cached_query(
    cache_key_func: Callable,
    ttl_seconds: int = 300
):
    """
    Decorator to cache query results.
    
    Args:
        cache_key_func: Function to generate cache key from function arguments
        ttl_seconds: Time to live for cache entries
    
    Example:
        @cached_query(lambda args, kwargs: f"user_{kwargs['user_id']}")
        def get_user_data(user_id: str):
            ...
    """
    cache: Dict[str, tuple] = {}  # {key: (result, expiry_time)}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = cache_key_func(args, kwargs)
            current_time = time.time()
            
            # Check cache
            if cache_key in cache:
                result, expiry = cache[cache_key]
                if current_time < expiry:
                    return result
                else:
                    del cache[cache_key]
            
            # Execute query
            result = func(*args, **kwargs)
            
            # Store in cache
            cache[cache_key] = (result, current_time + ttl_seconds)
            
            return result
        
        return wrapper
    return decorator

