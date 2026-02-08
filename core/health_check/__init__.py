"""
Health Check & Doctor - F1-10

Módulo de verificação de saúde do sistema e diagnóstico.
"""

from .doctor import (
    HealthCheck,
    HealthStatus,
    HealthCheckResult,
    ServiceHealth,
    SystemHealth,
    Doctor,
    run_health_check,
)

__all__ = [
    "HealthCheck",
    "HealthStatus",
    "HealthCheckResult",
    "ServiceHealth",
    "SystemHealth",
    "Doctor",
    "run_health_check",
]
