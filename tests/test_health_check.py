"""
Tests for Health Check & Doctor - F1-10
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from core.health_check.doctor import (
    Doctor,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    ServiceHealth,
    SystemHealth,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """Test status enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"

    def test_health_status_equality(self):
        """Test status comparison."""
        assert HealthStatus.HEALTHY == HealthStatus.HEALTHY
        assert HealthStatus.DEGRADED == HealthStatus.DEGRADED


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_create_healthy_result(self):
        """Test creating a healthy result."""
        result = HealthCheckResult(
            name="test_service",
            status=HealthStatus.HEALTHY,
            message="Service is healthy",
            details={"key": "value"},
        )

        assert result.name == "test_service"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Service is healthy"
        assert result.details == {"key": "value"}
        assert result.is_healthy is True

    def test_create_unhealthy_result(self):
        """Test creating an unhealthy result."""
        result = HealthCheckResult(
            name="test_service", status=HealthStatus.UNHEALTHY, message="Service is down"
        )

        assert result.is_healthy is False

    def test_create_degraded_result(self):
        """Test creating a degraded result."""
        result = HealthCheckResult(
            name="test_service", status=HealthStatus.DEGRADED, message="Service is degraded"
        )

        # DEGRADED ainda é considerado "healthy" para fins de continuidade
        assert result.is_healthy is True

    def test_result_timestamp(self):
        """Test result has timestamp."""
        result = HealthCheckResult(name="test", status=HealthStatus.HEALTHY, message="OK")
        assert result.timestamp is not None


class TestHealthCheck:
    """Tests for HealthCheck class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        hc = HealthCheck()

        assert "postgresql" in hc._check_functions
        assert "redis" in hc._check_functions
        assert "docker" in hc._check_functions
        assert "memory" in hc._check_functions
        assert "cpu" in hc._check_functions
        assert "disk" in hc._check_functions
        assert "network" in hc._check_functions
        assert "agent" in hc._check_functions

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        hc = HealthCheck(
            postgres_dsn="postgresql://user:pass@localhost:5432/custom",
            redis_url="redis://localhost:6379/5",
            docker_socket="/tmp/docker.sock",
        )

        assert "user:pass@localhost" in hc.postgres_dsn
        assert "localhost:6379/5" in hc.redis_url
        assert hc.docker_socket == "/tmp/docker.sock"

    def test_run_unknown_check(self):
        """Test running an unknown check."""
        hc = HealthCheck()
        result = hc.run_check("unknown_check")

        assert result.status == HealthStatus.UNKNOWN
        assert "não encontrada" in result.message
        assert "available" in result.details

    @patch("psycopg2.connect")
    def test_check_postgresql_healthy(self, mock_connect):
        """Test PostgreSQL check when healthy."""
        # Mock cursor and connection
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            "PostgreSQL 14.5",  # version()
            datetime.now(timezone.utc),  # pg_postmaster_start_time()
        ]
        mock_connect.return_value.cursor.return_value = mock_cursor
        mock_connect.return_value.close = MagicMock()

        hc = HealthCheck()
        result = hc.check_postgresql()

        # Result should be healthy or degraded (depending on datetime handling)
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert "postgresql" in result.name.lower()

    @patch("psycopg2.connect")
    def test_check_postgresql_unhealthy(self, mock_connect):
        """Test PostgreSQL check when unhealthy."""
        from psycopg2 import OperationalError

        mock_connect.side_effect = OperationalError("Connection refused")

        hc = HealthCheck()
        result = hc.check_postgresql()

        assert result.status == HealthStatus.UNHEALTHY
        assert "inacessível" in result.message.lower()

    @patch("redis.from_url")
    def test_check_redis_healthy(self, mock_redis):
        """Test Redis check when healthy."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"used_memory_human": "10M"}
        mock_redis.return_value = mock_client

        hc = HealthCheck()
        result = hc.check_redis()

        assert result.status == HealthStatus.HEALTHY
        assert "used_memory" in result.details

    @patch("redis.from_url")
    def test_check_redis_unhealthy(self, mock_redis):
        """Test Redis check when unhealthy."""
        from redis import ConnectionError as RedisConnectionError

        mock_redis.side_effect = RedisConnectionError("Connection refused")

        hc = HealthCheck()
        result = hc.check_redis()

        assert result.status == HealthStatus.UNHEALTHY

    def test_check_memory_unknown_when_psutil_missing(self):
        """Test memory check returns UNKNOWN when psutil is not available."""
        hc = HealthCheck()

        # Simular psutil não disponível
        with patch.dict("sys.modules", {"psutil": None}):
            result = hc.check_memory()
            assert result.status == HealthStatus.UNKNOWN

    def test_check_cpu_unknown_when_psutil_missing(self):
        """Test CPU check returns UNKNOWN when psutil is not available."""
        hc = HealthCheck()

        with patch.dict("sys.modules", {"psutil": None}):
            result = hc.check_cpu()
            assert result.status == HealthStatus.UNKNOWN

    def test_check_disk_unknown_when_psutil_missing(self):
        """Test disk check returns UNKNOWN when psutil is not available."""
        hc = HealthCheck()

        with patch.dict("sys.modules", {"psutil": None}):
            result = hc.check_disk()
            assert result.status == HealthStatus.UNKNOWN

    def test_check_network_healthy(self):
        """Test network check when healthy."""
        hc = HealthCheck()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock

            result = hc.check_network()

            assert result.status == HealthStatus.HEALTHY

    def test_get_overall_status_all_healthy(self):
        """Test getting overall status when all checks are healthy."""
        hc = HealthCheck()

        # Simular resultados todos healthy
        results = [
            HealthCheckResult(name="s1", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheckResult(name="s2", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheckResult(name="s3", status=HealthStatus.HEALTHY, message="OK"),
        ]

        status = hc.get_overall_status(results)
        assert status == HealthStatus.HEALTHY

    def test_get_overall_status_with_unhealthy(self):
        """Test getting overall status when one check is unhealthy."""
        hc = HealthCheck()

        results = [
            HealthCheckResult(name="s1", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheckResult(name="s2", status=HealthStatus.DEGRADED, message="Warning"),
            HealthCheckResult(name="s3", status=HealthStatus.UNHEALTHY, message="Critical"),
        ]

        status = hc.get_overall_status(results)
        assert status == HealthStatus.UNHEALTHY

    def test_get_overall_status_with_degraded(self):
        """Test getting overall status when checks are degraded."""
        hc = HealthCheck()

        results = [
            HealthCheckResult(name="s1", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheckResult(name="s2", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheckResult(name="s3", status=HealthStatus.DEGRADED, message="Warning"),
        ]

        status = hc.get_overall_status(results)
        assert status == HealthStatus.DEGRADED

    def test_get_overall_status_empty(self):
        """Test getting overall status with empty results."""
        hc = HealthCheck()

        status = hc.get_overall_status([])
        assert status == HealthStatus.UNKNOWN

    def test_run_all_checks(self):
        """Test running all checks."""
        hc = HealthCheck()
        results = hc.run_all_checks()

        # Deve ter pelo menos 8 checks
        assert len(results) >= 8

        # Cada resultado deve ter um nome
        for result in results:
            assert result.name is not None
            assert result.status is not None


class TestDoctor:
    """Tests for Doctor class."""

    def test_init(self):
        """Test Doctor initialization."""
        hc = HealthCheck()
        doctor = Doctor(hc)

        assert doctor.health_check is not None

    @patch.object(HealthCheck, "run_all_checks")
    def test_diagnose(self, mock_run_all):
        """Test diagnose method."""
        mock_run_all.return_value = [
            HealthCheckResult(name="postgresql", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheckResult(name="redis", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheckResult(name="memory", status=HealthStatus.HEALTHY, message="OK"),
        ]

        doctor = Doctor(HealthCheck())
        diagnosis = doctor.diagnose()

        assert "status" in diagnosis
        assert "checks" in diagnosis
        assert "recommendations" in diagnosis
        assert diagnosis["healthy_count"] == 3
        assert diagnosis["degraded_count"] == 0
        assert diagnosis["unhealthy_count"] == 0

    @patch.object(HealthCheck, "run_all_checks")
    def test_diagnose_with_unhealthy(self, mock_run_all):
        """Test diagnose with unhealthy service."""
        mock_run_all.return_value = [
            HealthCheckResult(name="memory", status=HealthStatus.UNHEALTHY, message="Critical"),
        ]

        doctor = Doctor(HealthCheck())
        diagnosis = doctor.diagnose()

        assert diagnosis["status"] == "unhealthy"
        assert len(diagnosis["recommendations"]) > 0
        assert "MEMORY CRITICAL" in diagnosis["recommendations"][0]

    @patch.object(HealthCheck, "run_check")
    def test_quick_check(self, mock_run):
        """Test quick_check method."""

        def side_effect(name):
            return HealthCheckResult(
                name=name, status=HealthStatus.HEALTHY, message="OK", details={}
            )

        mock_run.side_effect = side_effect

        doctor = Doctor(HealthCheck())
        result = doctor.quick_check()

        assert result.name == "quick_check"
        assert "4/4" in result.message

    @patch.object(HealthCheck, "run_check")
    def test_get_service_health(self, mock_run):
        """Test get_service_health method."""

        def side_effect(name):
            return HealthCheckResult(
                name=name, status=HealthStatus.HEALTHY, message="OK", details={}
            )

        mock_run.side_effect = side_effect

        doctor = Doctor(HealthCheck())
        services = doctor.get_service_health()

        assert len(services) == 3
        assert any(s.name == "postgresql" for s in services)
        assert any(s.name == "redis" for s in services)
        assert any(s.name == "docker" for s in services)


class TestRunHealthCheck:
    """Tests for run_health_check function."""

    @pytest.mark.asyncio
    async def test_run_health_check_quick(self):
        """Test quick health check."""
        from core.health_check.doctor import run_health_check

        with patch.object(HealthCheck, "run_all_checks") as mock:
            mock.return_value = [
                HealthCheckResult(name="p", status=HealthStatus.HEALTHY, message="OK"),
                HealthCheckResult(name="r", status=HealthStatus.HEALTHY, message="OK"),
                HealthCheckResult(name="m", status=HealthStatus.HEALTHY, message="OK"),
                HealthCheckResult(name="c", status=HealthStatus.HEALTHY, message="OK"),
            ]

            result = await run_health_check(full=False)

            assert "status" in result
            assert "message" in result
            assert "details" in result

    def test_run_health_check_sync(self):
        """Test health check sync wrapper."""
        import asyncio

        from core.health_check.doctor import run_health_check

        # Deve funcionar tanto síncrona quanto assincronamente
        result = asyncio.get_event_loop().run_until_complete(run_health_check(full=False))

        assert "status" in result


class TestServiceHealth:
    """Tests for ServiceHealth dataclass."""

    def test_create_service_health(self):
        """Test creating ServiceHealth."""
        health = ServiceHealth(
            name="postgresql", status=HealthStatus.HEALTHY, port=5432, version="14.5"
        )

        assert health.name == "postgresql"
        assert health.status == HealthStatus.HEALTHY
        assert health.port == 5432
        assert health.version == "14.5"


class TestSystemHealth:
    """Tests for SystemHealth dataclass."""

    def test_create_system_health(self):
        """Test creating SystemHealth."""
        health = SystemHealth(
            cpu_percent=50.0,
            memory_percent=60.0,
            disk_percent=70.0,
            network_connections=100,
            open_files=500,
        )

        assert health.cpu_percent == 50.0
        assert health.memory_percent == 60.0
        assert health.disk_percent == 70.0
        assert health.network_connections == 100
        assert health.open_files == 500
