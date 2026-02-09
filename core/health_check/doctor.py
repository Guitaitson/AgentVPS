"""
Health Check & Doctor - F1-10

Sistema de verificação de saúde do agente e diagnóstico.
Provides comprehensive health checks for services, system resources, and agent status.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class HealthStatus(Enum):
    """Status de saúde do componente."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Resultado de uma verificação de saúde."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        """Verifica se está saudável."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


@dataclass
class ServiceHealth:
    """Status de um serviço."""
    name: str
    status: HealthStatus
    port: Optional[int] = None
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Status de recursos do sistema."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_connections: int = 0
    open_files: int = 0
    load_average: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


class HealthCheck:
    """
    Verificações de saúde para o agente.

    Provides methods to check:
    - PostgreSQL connection
    - Redis connection
    - Docker services
    - System resources (RAM, CPU, disk)
    - Network connectivity
    - Agent-specific health checks
    """

    # Configurações de limiares
    MEMORY_WARNING_THRESHOLD = 75.0
    MEMORY_CRITICAL_THRESHOLD = 90.0
    CPU_WARNING_THRESHOLD = 70.0
    CPU_CRITICAL_THRESHOLD = 90.0
    DISK_WARNING_THRESHOLD = 80.0
    DISK_CRITICAL_THRESHOLD = 95.0

    def __init__(
        self,
        postgres_dsn: Optional[str] = None,
        redis_url: Optional[str] = None,
        docker_socket: Optional[str] = None,
    ):
        """
        Inicializa o health check.

        Args:
            postgres_dsn: Data Source Name para PostgreSQL
            redis_url: URL de conexão para Redis
            docker_socket: Socket do Docker
        """
        self.postgres_dsn = postgres_dsn or os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/agentvps")
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.docker_socket = docker_socket or os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")

        self._check_functions: Dict[str, Callable] = {}
        self._register_default_checks()

    def _register_default_checks(self):
        """Registra as verificações padrão."""
        self._check_functions = {
            "postgresql": self.check_postgresql,
            "redis": self.check_redis,
            "docker": self.check_docker,
            "memory": self.check_memory,
            "cpu": self.check_cpu,
            "disk": self.check_disk,
            "network": self.check_network,
            "agent": self.check_agent,
        }

    def check_postgresql(self) -> HealthCheckResult:
        """Verifica conexão com PostgreSQL."""
        import psycopg2
        from psycopg2 import OperationalError

        try:
            conn = psycopg2.connect(self.postgres_dsn, connect_timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.execute("SELECT pg_postmaster_start_time();")
            uptime = cursor.fetchone()[0]
            uptime_seconds = (datetime.now(timezone.utc) - uptime).total_seconds()
            conn.close()

            return HealthCheckResult(
                name="postgresql",
                status=HealthStatus.HEALTHY,
                message="PostgreSQL está operando normalmente",
                details={
                    "version": version,
                    "uptime_seconds": uptime_seconds,
                    "dsn": self.postgres_dsn.split("@")[0] + "@...",  # Mask credentials
                }
            )
        except OperationalError as e:
            return HealthCheckResult(
                name="postgresql",
                status=HealthStatus.UNHEALTHY,
                message=f"PostgreSQL inacessível: {str(e)}",
                details={"error": str(e)}
            )
        except Exception as e:
            return HealthCheckResult(
                name="postgresql",
                status=HealthStatus.DEGRADED,
                message=f"PostgreSQL com problema: {str(e)}",
                details={"error": str(e)}
            )

    def check_redis(self) -> HealthCheckResult:
        """Verifica conexão com Redis."""
        import redis
        from redis import ConnectionError as RedisConnectionError

        try:
            client = redis.from_url(self.redis_url, socket_timeout=5, socket_connect_timeout=5)
            client.ping()

            info = client.info("memory")
            used_memory = info.get("used_memory_human", "unknown")

            return HealthCheckResult(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis está operando normalmente",
                details={
                    "url": self.redis_url.split("@")[0] + "@...",
                    "used_memory": used_memory,
                }
            )
        except RedisConnectionError as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis inacessível: {str(e)}",
                details={"error": str(e)}
            )
        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.DEGRADED,
                message=f"Redis com problema: {str(e)}",
                details={"error": str(e)}
            )

    def check_docker(self) -> HealthCheckResult:
        """Verifica status do Docker."""
        import docker
        from docker.errors import DockerException

        try:
            client = docker.DockerSocketTimeoutError(
                base_url=self.docker_socket, timeout=5
            )
            client.ping()

            info = client.info()
            containers = client.containers.list(all=True)

            running = len([c for c in containers if c.status == "running"])
            stopped = len([c for c in containers if c.status != "running"])

            return HealthCheckResult(
                name="docker",
                status=HealthStatus.HEALTHY,
                message="Docker está operando normalmente",
                details={
                    "version": info.get("ServerVersion", "unknown"),
                    "containers_running": running,
                    "containers_stopped": stopped,
                    "total_containers": len(containers),
                }
            )
        except DockerException as e:
            return HealthCheckResult(
                name="docker",
                status=HealthStatus.UNHEALTHY,
                message=f"Docker inacessível: {str(e)}",
                details={"error": str(e)}
            )
        except Exception as e:
            return HealthCheckResult(
                name="docker",
                status=HealthStatus.DEGRADED,
                message=f"Docker com problema: {str(e)}",
                details={"error": str(e)}
            )

    def check_memory(self) -> HealthCheckResult:
        """Verifica uso de memória."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            percent = memory.percent

            if percent >= self.MEMORY_CRITICAL_THRESHOLD:
                status = HealthStatus.UNHEALTHY
                message = f"Memória crítica: {percent:.1f}% usado"
            elif percent >= self.MEMORY_WARNING_THRESHOLD:
                status = HealthStatus.DEGRADED
                message = f"Memória elevada: {percent:.1f}% usado"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memória normal: {percent:.1f}% usado"

            return HealthCheckResult(
                name="memory",
                status=status,
                message=message,
                details={
                    "percent": percent,
                    "used_gb": memory.used / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "total_gb": memory.total / (1024**3),
                }
            )
        except ImportError:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="psutil não disponível",
                details={}
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.DEGRADED,
                message=f"Erro ao verificar memória: {str(e)}",
                details={"error": str(e)}
            )

    def check_cpu(self) -> HealthCheckResult:
        """Verifica uso de CPU."""
        try:
            import psutil

            percent = psutil.cpu_percent(interval=1)

            if percent >= self.CPU_CRITICAL_THRESHOLD:
                status = HealthStatus.UNHEALTHY
                message = f"CPU crítica: {percent:.1f}% usado"
            elif percent >= self.CPU_WARNING_THRESHOLD:
                status = HealthStatus.DEGRADED
                message = f"CPU elevada: {percent:.1f}% usado"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU normal: {percent:.1f}% usado"

            return HealthCheckResult(
                name="cpu",
                status=status,
                message=message,
                details={
                    "percent": percent,
                    "cores": psutil.cpu_count(),
                    "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
                }
            )
        except ImportError:
            return HealthCheckResult(
                name="cpu",
                status=HealthStatus.UNKNOWN,
                message="psutil não disponível",
                details={}
            )
        except Exception as e:
            return HealthCheckResult(
                name="cpu",
                status=HealthStatus.DEGRADED,
                message=f"Erro ao verificar CPU: {str(e)}",
                details={"error": str(e)}
            )

    def check_disk(self) -> HealthCheckResult:
        """Verifica uso de disco."""
        try:
            import psutil

            disk = psutil.disk_usage("/")
            percent = disk.percent

            if percent >= self.DISK_CRITICAL_THRESHOLD:
                status = HealthStatus.UNHEALTHY
                message = f"Disco crítico: {percent:.1f}% usado"
            elif percent >= self.DISK_WARNING_THRESHOLD:
                status = HealthStatus.DEGRADED
                message = f"Disco elevado: {percent:.1f}% usado"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disco normal: {percent:.1f}% usado"

            return HealthCheckResult(
                name="disk",
                status=status,
                message=message,
                details={
                    "percent": percent,
                    "used_gb": disk.used / (1024**3),
                    "free_gb": disk.free / (1024**3),
                    "total_gb": disk.total / (1024**3),
                }
            )
        except ImportError:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.UNKNOWN,
                message="psutil não disponível",
                details={}
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.DEGRADED,
                message=f"Erro ao verificar disco: {str(e)}",
                details={"error": str(e)}
            )

    def check_network(self) -> HealthCheckResult:
        """Verifica conectividade de rede."""
        try:
            # Verificar conectividade externa
            import socket

            hosts_to_check = [
                ("8.8.8.8", 53, "DNS Google"),
                ("1.1.1.1", 53, "DNS Cloudflare"),
            ]

            results = []
            for host, port, description in hosts_to_check:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    results.append((description, result == 0))
                except Exception:
                    results.append((description, False))

            all_healthy = all(r[1] for r in results)

            if all_healthy:
                status = HealthStatus.HEALTHY
                message = "Conectividade de rede normal"
            else:
                failed = [r[0] for r in results if not r[1]]
                status = HealthStatus.DEGRADED
                message = f"Conectividade comprometida: {', '.join(failed)}"

            return HealthCheckResult(
                name="network",
                status=status,
                message=message,
                details=dict(results),
            )
        except Exception as e:
            return HealthCheckResult(
                name="network",
                status=HealthStatus.DEGRADED,
                message=f"Erro ao verificar rede: {str(e)}",
                details={"error": str(e)}
            )

    def check_agent(self) -> HealthCheckResult:
        """Verifica saúde do agente."""
        try:
            import os
            from datetime import datetime, timezone

            # Verificar se processos essenciais estão rodando
            checks = {
                "agent_running": os.path.exists("/opt/vps-agent/.running"),
                "config_exists": os.path.exists("/opt/vps-agent/.env"),
                "logs_accessible": os.path.exists("/opt/vps-agent/logs"),
            }

            all_healthy = all(checks.values())

            if all_healthy:
                status = HealthStatus.HEALTHY
                message = "Agente operando normalmente"
            else:
                failed = [k for k, v in checks.items() if not v]
                status = HealthStatus.DEGRADED
                message = f"Agente com problemas: {', '.join(failed)}"

            return HealthCheckResult(
                name="agent",
                status=status,
                message=message,
                details={
                    **checks,
                    "python_version": __import__("sys").version.split()[0],
                    "check_time": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="agent",
                status=HealthStatus.DEGRADED,
                message=f"Erro ao verificar agente: {str(e)}",
                details={"error": str(e)}
            )

    def run_check(self, check_name: str) -> HealthCheckResult:
        """Executa uma verificação específica."""
        if check_name not in self._check_functions:
            return HealthCheckResult(
                name=check_name,
                status=HealthStatus.UNKNOWN,
                message=f"Verificação '{check_name}' não encontrada",
                details={"available": list(self._check_functions.keys())}
            )

        return self._check_functions[check_name]()

    def run_all_checks(self) -> List[HealthCheckResult]:
        """Executa todas as verificações."""
        results = []
        for check_name in self._check_functions:
            results.append(self.run_check(check_name))
        return results

    def get_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """Determina status geral baseado nos resultados."""
        if not results:
            return HealthStatus.UNKNOWN

        # Se algum estiver UNHEALTHY, status geral é UNHEALTHY
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            return HealthStatus.UNHEALTHY

        # Se algum estiver DEGRADED, status geral é DEGRADED
        if any(r.status == HealthStatus.DEGRADED for r in results):
            return HealthStatus.DEGRADED

        # Se todos estiverem HEALTHY, status geral é HEALTHY
        if all(r.status == HealthStatus.HEALTHY for r in results):
            return HealthStatus.HEALTHY

        return HealthStatus.DEGRADED


class Doctor:
    """
    Doctor - Diagnostic tool for the agent.

    Provides comprehensive health reports and recommendations.
    """

    def __init__(self, health_check: Optional[HealthCheck] = None):
        """Initialize the doctor."""
        self.health_check = health_check or HealthCheck()

    def diagnose(self) -> Dict[str, Any]:
        """
        Run comprehensive diagnosis.

        Returns:
            Dict with overall status, results, and recommendations.
        """
        results = self.health_check.run_all_checks()
        overall_status = self.health_check.get_overall_status(results)

        recommendations = self._generate_recommendations(results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                r.name: {
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in results
            },
            "recommendations": recommendations,
            "healthy_count": len([r for r in results if r.status == HealthStatus.HEALTHY]),
            "degraded_count": len([r for r in results if r.status == HealthStatus.DEGRADED]),
            "unhealthy_count": len([r for r in results if r.status == HealthStatus.UNHEALTHY]),
        }

    def _generate_recommendations(self, results: List[HealthCheckResult]) -> List[str]:
        """Generate recommendations based on check results."""
        recommendations = []

        for result in results:
            if result.status == HealthStatus.UNHEALTHY:
                if result.name == "memory":
                    recommendations.append("🧠 MEMORY CRITICAL: Considere liberar memória ou reiniciar serviços não essenciais")
                elif result.name == "cpu":
                    recommendations.append("💻 CPU CRITICAL: Verifique processos em execução e considere escalar")
                elif result.name == "disk":
                    recommendations.append("💾 DISK CRITICAL: Limpe arquivos temporários e logs antigos")
                elif result.name == "postgresql":
                    recommendations.append("🐘 PostgreSQL inacessível: Verifique se o container está rodando")
                elif result.name == "redis":
                    recommendations.append("🔴 Redis inacessível: Verifique se o container está rodando")
                elif result.name == "docker":
                    recommendations.append("🐳 Docker inacessível: Verifique o serviço Docker")
            elif result.status == HealthStatus.DEGRADED:
                if result.name == "memory":
                    recommendations.append("🧠 Memory elevada: Monitorar uso de memória")
                elif result.name == "cpu":
                    recommendations.append("💻 CPU elevada: Monitorar processos")
                elif result.name == "disk":
                    recommendations.append("💾 Disco elevado: Planejar limpeza de disco")
                elif result.name == "network":
                    recommendations.append("🌐 Rede comprometida: Verificar conectividade")

        return recommendations

    def quick_check(self) -> HealthCheckResult:
        """Run quick health check (core services only)."""
        checks = ["postgresql", "redis", "memory", "cpu"]
        results = []

        for check in checks:
            if check in self.health_check._check_functions:
                results.append(self.health_check.run_check(check))

        overall_status = self.health_check.get_overall_status(results)
        healthy_count = len([r for r in results if r.status == HealthStatus.HEALTHY])
        total_count = len(results)

        return HealthCheckResult(
            name="quick_check",
            status=overall_status,
            message=f"Quick check: {healthy_count}/{total_count} serviços saudáveis",
            details={
                "results": {r.name: r.status.value for r in results},
                "healthy_count": healthy_count,
                "total_count": total_count,
            }
        )

    def get_service_health(self) -> List[ServiceHealth]:
        """Get health status of all services."""
        services = ["postgresql", "redis", "docker"]
        health_list = []

        for service_name in services:
            result = self.health_check.run_check(service_name)
            health = ServiceHealth(
                name=service_name,
                status=result.status,
                details=result.details,
            )
            health_list.append(health)

        return health_list

    def get_system_health(self) -> SystemHealth:
        """Get system resource health."""
        memory_result = self.health_check.run_check("memory")
        cpu_result = self.health_check.run_check("cpu")
        disk_result = self.health_check.run_check("disk")

        return SystemHealth(
            cpu_percent=cpu_result.details.get("percent", 0),
            memory_percent=memory_result.details.get("percent", 0),
            disk_percent=disk_result.details.get("percent", 0),
            details={
                "memory": memory_result.details,
                "cpu": cpu_result.details,
                "disk": disk_result.details,
            }
        )


async def run_health_check(
    postgres_dsn: Optional[str] = None,
    redis_url: Optional[str] = None,
    full: bool = False,
) -> Dict[str, Any]:
    """
    Run health check (sync or async wrapper).

    Args:
        postgres_dsn: PostgreSQL connection string
        redis_url: Redis connection URL
        full: Run full check or quick check

    Returns:
        Health check results
    """
    doctor = Doctor(HealthCheck(postgres_dsn, redis_url))

    if full:
        return doctor.diagnose()
    else:
        result = doctor.quick_check()
        return {
            "status": result.status.value,
            "message": result.message,
            "details": result.details,
        }
