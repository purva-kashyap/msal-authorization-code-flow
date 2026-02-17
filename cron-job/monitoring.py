"""
Monitoring and metrics collection using Prometheus.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from typing import Callable
import time
import functools


# Metrics
meetings_processed_total = Counter(
    'meetings_processed_total',
    'Total number of meetings processed',
    ['platform', 'status']
)

meetings_processing_duration = Histogram(
    'meetings_processing_duration_seconds',
    'Time spent processing meetings',
    ['platform']
)

api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests made',
    ['platform', 'endpoint', 'status']
)

api_request_duration = Histogram(
    'api_request_duration_seconds',
    'Duration of API requests',
    ['platform', 'endpoint']
)

transcript_downloads_total = Counter(
    'transcript_downloads_total',
    'Total number of transcripts downloaded',
    ['platform', 'status']
)

summary_generations_total = Counter(
    'summary_generations_total',
    'Total number of summaries generated',
    ['status']
)

cron_job_runs_total = Counter(
    'cron_job_runs_total',
    'Total number of cron job executions',
    ['status']
)

cron_job_duration = Histogram(
    'cron_job_duration_seconds',
    'Duration of cron job executions'
)

active_users_gauge = Gauge(
    'active_users_total',
    'Number of active users being processed'
)

database_operations_total = Counter(
    'database_operations_total',
    'Total number of database operations',
    ['operation', 'status']
)

errors_total = Counter(
    'errors_total',
    'Total number of errors by type',
    ['error_type', 'component']
)


def track_time(metric: Histogram, labels: dict = None):
    """
    Decorator to track execution time of a function.
    
    Args:
        metric: Prometheus Histogram metric
        labels: Optional labels for the metric
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
        
        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def get_metrics() -> bytes:
    """
    Get current metrics in Prometheus format.
    
    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest(REGISTRY)


def record_error(error_type: str, component: str):
    """
    Record an error occurrence.
    
    Args:
        error_type: Type of error (e.g., 'TokenExpiredError')
        component: Component where error occurred (e.g., 'teams_service')
    """
    errors_total.labels(error_type=error_type, component=component).inc()
