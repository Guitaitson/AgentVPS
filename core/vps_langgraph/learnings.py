# Learnings Manager - Sistema de registro de aprendizados

"""
Módulo para registrar e consultar aprendizados do agente.

Este módulo implementa a recomendação do Opus 4.6:
"Tabela 'learnings' no PostgreSQL para registrar falhas e lições"

Estrutura da tabela learnings:
| id | category | trigger | lesson | created_at |
|----|----------|---------|--------|------------|
| 1  | api_failure | github_api_rate_limit | Usar token PAT, não basic auth | 2026-02-08 |
| 2  | tool_choice | web_search | Brave Search > Google Custom Search | 2026-02-09 |
"""

import json
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


# Conexão com PostgreSQL
def get_db_connection():
    """Retorna conexão com PostgreSQL."""
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "vps_agent"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        connect_timeout=5
    )


@contextmanager
def db_cursor():
    """Context manager para cursor do banco."""
    conn = get_db_connection()
    try:
        yield conn.cursor()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_learnings_table():
    """
    Inicializa a tabela learnings se não existir.

    Returns:
        True se a tabela foi criada com sucesso
    """
    create_sql = """
    CREATE TABLE IF NOT EXISTS learnings (
        id SERIAL PRIMARY KEY,
        category VARCHAR(100) NOT NULL,
        trigger TEXT NOT NULL,
        lesson TEXT NOT NULL,
        success BOOLEAN DEFAULT TRUE,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

        -- Índices para busca eficiente
        CONSTRAINT learnings_category_check CHECK (category IN (
            'api_failure', 'tool_choice', 'execution_error',
            'user_feedback', 'system_learning', 'security'
        ))
    );

    -- Índice para buscar por categoria
    CREATE INDEX IF NOT EXISTS learnings_category_idx ON learnings(category);

    -- Índice para buscar por gatilho (uso de texto simples)
    CREATE INDEX IF NOT EXISTS learnings_trigger_idx ON learnings USING gin(to_tsvector('portuguese', trigger));

    -- Índice para buscar por lição
    CREATE INDEX IF NOT EXISTS learnings_lesson_idx ON learnings USING gin(to_tsvector('portuguese', lesson));
    """

    try:
        with db_cursor() as cursor:
            cursor.execute(create_sql)
        logger.info("learnings_table_initialized")
        return True
    except Exception as e:
        logger.error("learnings_table_init_failed", error=str(e))
        return False


class LearningsManager:
    """Gerenciador de aprendizados do agente."""

    def __init__(self):
        """Inicializa o gerenciador."""
        self._initialized = False

    def ensure_initialized(self):
        """Garante que a tabela existe."""
        if not self._initialized:
            init_learnings_table()
            self._initialized = True

    def add_learning(
        self,
        category: str,
        trigger: str,
        lesson: str,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Adiciona um novo aprendizado.

        Args:
            category: Categoria do aprendizado
            trigger: O que disparou o aprendizado
            lesson: O que foi aprendido
            success: Se foi um sucesso ou falha
            metadata: Metadados adicionais

        Returns:
            ID do aprendizado criado
        """
        self.ensure_initialized()

        insert_sql = """
        INSERT INTO learnings (category, trigger, lesson, success, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """

        try:
            with db_cursor() as cursor:
                cursor.execute(
                    insert_sql,
                    (category, trigger, lesson, success, json.dumps(metadata or {}))
                )
                result = cursor.fetchone()
                learning_id = result[0] if result else None

            logger.info(
                "learning_added",
                category=category,
                learning_id=learning_id,
                success=success
            )
            return learning_id

        except Exception as e:
            logger.error("learning_add_failed", error=str(e))
            return -1

    def get_learnings(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Recupera aprendizados.

        Args:
            category: Filtrar por categoria (opcional)
            limit: Número máximo de resultados
            offset: Deslocamento para paginação

        Returns:
            Lista de aprendizados
        """
        self.ensure_initialized()

        if category:
            query = "SELECT * FROM learnings WHERE category = %s ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params = (category, limit, offset)
        else:
            query = "SELECT * FROM learnings ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params = (limit, offset)

        try:
            with db_cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

                columns = ['id', 'category', 'trigger', 'lesson', 'success',
                          'metadata', 'created_at']
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error("learnings_fetch_failed", error=str(e))
            return []

    def search_learnings(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca aprendizados por palavra-chave.

        Args:
            query: Termo de busca
            limit: Número máximo de resultados

        Returns:
            Lista de aprendizados encontrados
        """
        self.ensure_initialized()

        search_sql = """
        SELECT * FROM learnings
        WHERE trigger ILIKE %s OR lesson ILIKE %s
        ORDER BY created_at DESC
        LIMIT %s
        """

        try:
            with db_cursor() as cursor:
                cursor.execute(search_sql, (f"%{query}%", f"%{query}%", limit))
                rows = cursor.fetchall()

                columns = ['id', 'category', 'trigger', 'lesson', 'success',
                          'metadata', 'created_at']
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error("learnings_search_failed", error=str(e))
            return []

    def get_recent_failures(self, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Recupera falhas recentes para análise.

        Args:
            days: Número de dias para buscar
            limit: Número máximo de resultados

        Returns:
            Lista de falhas recentes
        """
        self.ensure_initialized()

        query = """
        SELECT * FROM learnings
        WHERE success = FALSE
        AND created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
        LIMIT %s
        """

        try:
            with db_cursor() as cursor:
                cursor.execute(query, (days, limit))
                rows = cursor.fetchall()

                columns = ['id', 'category', 'trigger', 'lesson', 'success',
                          'metadata', 'created_at']
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error("failures_fetch_failed", error=str(e))
            return []

    def get_lessons_for_action(
        self,
        action_type: str,
        context: str = ""
    ) -> List[str]:
        """
        Recupera lições relevantes antes de executar uma ação.

        Args:
            action_type: Tipo de ação (ex: 'github_api', 'web_search')
            context: Contexto adicional da ação

        Returns:
            Lista de lições aprendidas
        """
        # Buscar por categoria ou gatilho relacionado
        learnings = self.search_learnings(action_type, limit=5)

        # Se não encontrou, buscar por contexto
        if not learnings and context:
            learnings = self.search_learnings(context, limit=5)

        # Filtrar apenas lições relevantes (sucesso = True)
        relevant_lessons = [
            lesson_item['lesson'] for lesson_item in learnings
            if lesson_item['success'] and lesson_item['category'] != 'execution_error'
        ]

        return relevant_lessons

    def record_api_failure(
        self,
        api_name: str,
        error: str,
        suggestion: str = ""
    ) -> int:
        """
        Registra falha de API específica.

        Args:
            api_name: Nome da API que falhou
            error: Erro ocorrido
            suggestion: Sugestão de solução

        Returns:
            ID do aprendizado criado
        """
        return self.add_learning(
            category="api_failure",
            trigger=f"API: {api_name} | Erro: {error[:200]}",
            lesson=suggestion or f"API {api_name} falhou com erro: {error[:200]}",
            success=False,
            metadata={"api_name": api_name, "error": error[:500]}
        )

    def record_tool_choice(
        self,
        tool: str,
        reason: str,
        outcome: str
    ) -> int:
        """
        Registra escolha de ferramenta e seu resultado.

        Args:
            tool: Ferramenta escolhida
            reason: Razão da escolha
            outcome: Resultado da execução

        Returns:
            ID do aprendizado criado
        """
        return self.add_learning(
            category="tool_choice",
            trigger=f"Ferramenta: {tool} | Razão: {reason[:200]}",
            lesson=f"Resultado: {outcome[:500]}",
            success="sucesso" in outcome.lower() or "funcionou" in outcome.lower(),
            metadata={"tool": tool, "reason": reason[:500]}
        )

    def get_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo dos aprendizados.

        Returns:
            Dicionário com estatísticas
        """
        self.ensure_initialized()

        query = """
        SELECT
            category,
            COUNT(*) as total,
            SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as successes,
            SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as failures,
            MIN(created_at) as oldest,
            MAX(created_at) as newest
        FROM learnings
        GROUP BY category
        ORDER BY total DESC
        """

        try:
            with db_cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                categories = {}
                for row in rows:
                    categories[row[0]] = {
                        "total": row[1],
                        "successes": row[2],
                        "failures": row[3],
                        "oldest": row[4].isoformat() if row[4] else None,
                        "newest": row[5].isoformat() if row[5] else None
                    }

                return {
                    "total_learnings": sum(c["total"] for c in categories.values()),
                    "categories": categories,
                    "initialized": self._initialized
                }

        except Exception as e:
            logger.error("learnings_summary_failed", error=str(e))
            return {"error": str(e)}


# Instância global do gerenciador
learnings_manager = LearningsManager()


# ============ Convenience Functions ============

def record_failure_and_continue(api_name: str, error: str, suggestion: str = ""):
    """
    Registra falha e retorna lições aprendidas anteriormente.

    Args:
        api_name: Nome da API que falhou
        error: Erro ocorrido
        suggestion: Sugestão de solução

    Returns:
        Lista de lições aprendidas anteriormente
    """
    # Registrar a falha
    learnings_manager.record_api_failure(api_name, error, suggestion)

    # Buscar lições anteriores
    return learnings_manager.get_lessons_for_action(api_name)


def check_before_action(action_type: str, context: str = "") -> Dict[str, Any]:
    """
    Verifica lições aprendidas antes de executar uma ação.

    Args:
        action_type: Tipo da ação
        context: Contexto adicional

    Returns:
        Dicionário com lições relevantes
    """
    lessons = learnings_manager.get_lessons_for_action(action_type, context)

    return {
        "action": action_type,
        "has_lessons": len(lessons) > 0,
        "lessons": lessons,
        "recommendation": (
            f"Encontrei {len(lessons)} lição(ões) anterior(es) para '{action_type}'. "
            "Recomendo revisar antes de continuar."
            if lessons else
            "Sem lições anteriores. Primeira execução desta ação."
        )
    }
