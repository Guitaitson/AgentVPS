"""
OpenTelemetry Observability - Sprint 3

Módulo de observabilidade para traces, métricas e logs.
Integração com LangGraph e Telegram Bot.

Este módulo é OPCIONAL - funciona apenas se opentelemetry estiver instalado.
"""

from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Optional

# Imports opcionais - se não tiver, usa fallback
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.trace import Status, StatusCode
    _OPENTELEMETRY_AVAILABLE = True
except ImportError:
    _OPENTELEMETRY_AVAILABLE = False
    # Stub para quando não tiver opentelemetry
    class MockSpan:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def set_status(self, *args, **kwargs): pass
        def record_exception(self, *args): pass
        def set_attribute(self, *args, **kwargs): pass
        def add_event(self, *args, **kwargs): pass
    
    class MockTracer:
        def start_as_current_span(self, name): return MockSpan()
        def start_span(self, name): return MockSpan()
    
    class MockTrace:
        def get_tracer(self, *args): return MockTracer()
    
    trace = MockTrace()
    # Tipos para compatibilidade - devem ser callable
    class MockStatus:
        def __init__(self, code=None, description=None):
            pass
        OK = 'ok'
        ERROR = 'error'
    
    def make_status(code):
        return MockStatus(code)
    
    Status = make_status
    StatusCode = MockStatus()
    # Mock Tracer type
    class MockTracerClass:
        pass
    trace.Tracer = MockTracerClass


# Configuração global
_tracer: Optional[trace.Tracer] = None
_enabled: bool = False


def init_observability(
    service_name: str = "vps-agent",
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
) -> None:
    """
    Inicializa o OpenTelemetry.
    
    Args:
        service_name: Nome do serviço
        otlp_endpoint: Endpoint do OTLP Collector (opcional)
        console_export: Exporter para console (debug)
    """
    global _tracer, _enabled
    
    # Se opentelemetry não disponível, apenas marca como enabled
    if not _OPENTELEMETRY_AVAILABLE:
        _enabled = True
        return
    
    # Criar resource
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "service.version": "2.0.0",
    })
    
    # Configurar provider
    provider = TracerProvider(resource=resource)
    
    # Adicionar exporters
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanExporter(exporter))
    
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)
    _enabled = True


def get_tracer() -> trace.Tracer:
    """Retorna o tracer global."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__)
    return _tracer


def trace_async(name: str = None):
    """
    Decorador para traced functions async.
    
    Uso:
        @trace_async("minha_funcao")
        async def minha_funcao():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            span_name = name or func.__name__
            
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def trace_sync(name: str = None):
    """
    Decorador para traced functions sync.
    
    Uso:
        @trace_sync("minha_funcao")
        def minha_funcao():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            span_name = name or func.__name__
            
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


def add_event(name: str, attributes: dict = None) -> None:
    """Adiciona um evento ao span atual."""
    tracer = get_tracer()
    with tracer.start_as_current_span("event") as span:
        span.add_event(name, attributes=attributes or {})


def set_attribute(key: str, value: Any) -> None:
    """Define um atributo no span atual."""
    tracer = get_tracer()
    with tracer.start_as_current_span("attribute") as span:
        span.set_attribute(key, value)


class ObservabilityContext:
    """
    Contexto de observabilidade para operations.
    
    Uso:
        async with ObservabilityContext("minha_operacao", {"key": "value"}):
            # código monitored
            ...
    """
    
    def __init__(self, name: str, attributes: dict = None):
        self.name = name
        self.attributes = attributes or {}
    
    @asynccontextmanager
    async def __aenter__(self):
        tracer = get_tracer()
        with tracer.start_as_current_span(self.name) as span:
            for key, value in self.attributes.items():
                span.set_attribute(key, value)
            yield span
    
    def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# Integração com LangGraph
class LangGraphObserver:
    """Observer para LangGraph - tracing de nodes."""
    
    def __init__(self, tracer: trace.Tracer):
        self.tracer = tracer
    
    def on_node_start(self, node_name: str, inputs: dict):
        """Called when a node starts."""
        span = self.tracer.start_span(f"langgraph.node.{node_name}")
        span.set_attribute("langgraph.node_type", "start")
        return span
    
    def on_node_end(self, node_name: str, outputs: dict, span):
        """Called when a node ends."""
        span.set_attribute("langgraph.node_type", "end")
        for key, value in outputs.items():
            span.set_attribute(f"langgraph.output.{key}", str(value)[:100])
        span.end()
    
    def on_node_error(self, node_name: str, error: Exception, span):
        """Called when a node errors."""
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)
        span.end()


# Convenience functions
def trace_llm_call(model: str, prompt_tokens: int = None, completion_tokens: int = None):
    """Decorator específico para calls de LLM."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(f"llm.{model}") as span:
                span.set_attribute("llm.model", model)
                if prompt_tokens:
                    span.set_attribute("llm.prompt_tokens", prompt_tokens)
                
                result = await func(*args, **kwargs)
                
                if completion_tokens:
                    span.set_attribute("llm.completion_tokens", completion_tokens)
                
                return result
        return wrapper
    return decorator


def trace_tool_call(tool_name: str):
    """Decorator específico para calls de tools."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(f"tool.{tool_name}") as span:
                span.set_attribute("tool.name", tool_name)
                span.set_attribute("tool.type", "execution")
                
                result = await func(*args, **kwargs)
                
                span.set_attribute("tool.completed", True)
                return result
        return wrapper
    return decorator


__all__ = [
    "init_observability",
    "get_tracer",
    "trace_async",
    "trace_sync",
    "add_event",
    "set_attribute",
    "ObservabilityContext",
    "LangGraphObserver",
    "trace_llm_call",
    "trace_tool_call",
]
