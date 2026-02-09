# Smart Responses - Respostas inteligentes quando habilidades faltam

"""
Módulo de respostas inteligentes para quando o agente não pode
executar uma solicitação diretamente.

Este módulo implementa a recomendação do Opus 4.6:
"Em vez de 'não tenho ferramenta direta', responder com plano de ação"
"""

from datetime import datetime

# Mapeamento de palavras-chave para descrições de habilidades
SKILL_GUIDE = {
    "github": {
        "name": "GitHub API",
        "description": "listar repositórios, criar PRs, gerenciar issues",
        "plan": [
            "1. Instalar/clonar SDK do GitHub",
            "2. Configurar token PAT (Personal Access Token)",
            "3. Implementar endpoints para listar/criar repos",
        ],
    },
    "repositório": {
        "name": "GitHub API",
        "description": "gerenciar repositórios GitHub",
        "plan": [
            "1. Instalar/clonar SDK do GitHub",
            "2. Configurar autenticação",
            "3. Implementar operações de repositório",
        ],
    },
    "web": {
        "name": "Busca Web",
        "description": "buscar informações na internet",
        "plan": [
            "1. Integrar API de busca (Brave Search)",
            "2. Implementar parser de resultados",
            "3. Adicionar cache de buscas",
        ],
    },
    "site": {
        "name": "Web Scraping",
        "description": "extrair conteúdo de páginas web",
        "plan": [
            "1. Implementar parser HTML",
            "2. Adicionar rate limiting",
            "3. Tratar erros de rede",
        ],
    },
    "arquivo": {
        "name": "Gerenciador de Arquivos",
        "description": "ler, criar e editar arquivos",
        "plan": [
            "1. Implementar operações de arquivo seguro",
            "2. Adicionar validação de caminhos",
            "3. Criar backup automático",
        ],
    },
    "banco": {
        "name": "Banco de Dados",
        "description": "executar queries SQL",
        "plan": [
            "1. Conectar ao PostgreSQL",
            "2. Implementar query builder seguro",
            "3. Adicionar validação de inputs",
        ],
    },
    "email": {
        "name": "Email",
        "description": "enviar e receber emails",
        "plan": [
            "1. Configurar servidor SMTP",
            "2. Implementar envio de emails",
            "3. Adicionar templates",
        ],
    },
    "slack": {
        "name": "Slack Integration",
        "description": "enviar mensagens para Slack",
        "plan": [
            "1. Configurar webhook do Slack",
            "2. Implementar envio de mensagens",
            "3. Adicionar formatação rica",
        ],
    },
    "criar": {
        "name": "Criação de Agentes",
        "description": "criar novos subagentes",
        "plan": [
            "1. Usar CLI Kilocode para criar agente",
            "2. Configurar ambiente isolado",
            "3. Integrar com LangGraph",
        ],
    },
    "agente": {
        "name": "Gerenciamento de Agentes",
        "description": "criar e gerenciar subagentes",
        "plan": [
            "1. Definir capacidades do agente",
            "2. Criar estrutura do projeto",
            "3. Configurar CI/CD",
        ],
    },
}


def detect_missing_skill_keywords(message: str) -> list:
    """
    Detecta palavras-chave que indicam habilidades faltantes.

    Args:
        message: Mensagem do usuário (já em lowercase)

    Returns:
        Lista de chaves de habilidades detectadas
    """
    detected = []
    for key in SKILL_GUIDE.keys():
        if key in message:
            detected.append(key)
    return detected


def generate_smart_unavailable_response(
    user_message: str, detected_skills: list = None, intent: str = "unknown"
) -> str:
    """
    Gera uma resposta inteligente quando uma habilidade não está disponível.

    Esta função implementa a recomendação do Opus 4.6:
    "Em vez de 'não tenho ferramenta direta', responder com plano de ação"

    Args:
        user_message: Mensagem original do usuário
        detected_skills: Lista de habilidades detectadas como faltantes
        intent: Intento classificado

    Returns:
        Resposta formatada com plano de ação
    """
    if detected_skills is None:
        detected_skills = detect_missing_skill_keywords(user_message.lower())

    if not detected_skills:
        # Resposta genérica quando não detecta skill específica
        return _generate_generic_unavailable_response(intent)

    # Criar resposta baseada nas habilidades detectadas
    responses = []
    responses.append("🤖 **Entendi sua solicitação!**")
    responses.append("")
    responses.append("Atualmente, não tenho a habilidade necessária instalada,")
    responses.append("mas posso implementá-la para você!")
    responses.append("")

    for skill_key in detected_skills:
        skill_info = SKILL_GUIDE.get(skill_key, {})
        if skill_info:
            responses.append(f"📦 **{skill_info['name']}**")
            responses.append(f"   O que faz: {skill_info['description']}")
            responses.append("   Para implementar:")
            for step in skill_info["plan"]:
                responses.append(f"   {step}")
            responses.append("")

    responses.append("⏱️ **Tempo estimado:** 2-4 horas")
    responses.append("")
    responses.append("Quer que eu registre isso como próxima melhoria?")
    responses.append("Posso criar um plano detalhado e implementar quando você aprovar. ✅")

    return "\n".join(responses)


def _generate_generic_unavailable_response(intent: str) -> str:
    """
    Gera resposta genérica quando não detecta skill específica.

    Args:
        intent: Intento classificado

    Returns:
        Resposta genérica formatada
    """
    responses = []
    responses.append("🤖 **Entendido!**")
    responses.append("")
    responses.append("Não tenho uma ferramenta específica para isso ainda,")
    responses.append("mas posso analisar e implementar o que você precisa!")
    responses.append("")

    if intent == "self_improve":
        responses.append("Detected que você quer criar ou implementar algo novo.")
        responses.append("Posso:")
        responses.append("• Criar uma nova skill/ferramenta")
        responses.append("• Integrar uma API externa")
        responses.append("• Desenvolver um novo agente")
        responses.append("")
        responses.append(
            "Me explique melhor o que você precisa e eu criarei um plano de implementação."
        )

    elif intent == "task":
        responses.append("Para executar essa tarefa, preciso:")
        responses.append("1. Entender exatamente o que você precisa")
        responses.append("2. Verificar se já tenho as ferramentas necessárias")
        responses.append("3. Se necessário, implementar nova funcionalidade")
        responses.append("")
        responses.append("Pode me dar mais detalhes sobre a tarefa?")

    else:
        responses.append("Posso aprender novas habilidades! 😊")
        responses.append("Me explique o que você precisa e eu criarei um plano para implementar.")

    responses.append("")
    responses.append("📝 **O que eu preciso saber:**")
    responses.append("• O que você quer alcançar?")
    responses.append("• Com quais sistemas/API preciso integrar?")
    responses.append("• Qual a frequência de uso?")

    return "\n".join(responses)


def generate_capability_detected_response(
    capability_name: str, is_implemented: bool = False
) -> str:
    """
    Gera resposta quando uma capacidade é detectada.

    Args:
        capability_name: Nome da capacidade
        is_implemented: Se já está implementada

    Returns:
        Resposta formatada
    """
    if is_implemented:
        return f"✅ **Capacidade disponível:** {capability_name}\n\nPosso ajudar com isso! O que você precisa?"

    return generate_smart_unavailable_response(
        f"preciso de {capability_name}", detect_missing_skill_keywords(capability_name.lower())
    )


# ============ Learning Tracking ============


def create_learning_message(category: str, trigger: str, lesson: str, success: bool = True) -> str:
    """
    Cria uma mensagem formatada para registrar um aprendizado.

    Args:
        category: Categoria do aprendizado (api_failure, tool_choice, etc.)
        trigger: O que disparou o aprendizado
        lesson: O que foi aprendido
        success: Se foi um sucesso ou falha

    Returns:
        Mensagem formatada para logging/registro
    """
    status = "✅" if success else "❌"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    return (
        f"{status} **Learning Registrado** [{timestamp}]\n"
        f"📂 Categoria: {category}\n"
        f"🔔 Gatilho: {trigger}\n"
        f"📚 Lição: {lesson}"
    )


# ============ Help and Capabilities Summary ============


def get_capabilities_summary() -> str:
    """
    Retorna resumo das capacidades atuais do agente.

    Returns:
        String formatada com resumo
    """
    return """
🎯 **Minhas Capacidades Atuais:**

✅ **Gerenciamento VPS:**
   • Status de RAM e CPU
   • Containers Docker (listar, iniciar, parar)
   • Serviços (PostgreSQL, Redis)

✅ **Memória:**
   • Memória estruturada (PostgreSQL)
   • Histórico de conversas

✅ **Comunicação:**
   • Interface Telegram

⚠️ **Em Desenvolvimento:**
   • GitHub API (breve)
   • Busca Web (breve)
   • CLI Execution (breve)

💡 **Posso evoluir!** Me peça para implementar novas funcionalidades!
"""
