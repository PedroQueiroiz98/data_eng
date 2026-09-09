"""Montagem das mensagens (system + user) por tarefa de IA."""

from __future__ import annotations

from nbplatform.domain.assistant import AssistantContext, AssistantTask, ChatMessage

SYSTEM_BASE = (
    "Você é um assistente de programação Python dentro de um editor de notebooks. "
    "Regras:\n"
    "- Responda SOMENTE com código, num único bloco cercado por ``` , a menos que "
    "a tarefa peça explicação.\n"
    "- Nunca invente APIs ou parâmetros; use apenas o que existe nas bibliotecas.\n"
    "- Respeite os imports e variáveis já presentes no contexto.\n"
    "- Não repita imports já feitos.\n"
    "- Português nas explicações."
)

_INLINE_SYSTEM = (
    "Complete o código Python na posição do cursor. Responda SOMENTE com o trecho "
    "que vem a seguir (sem cercas de código, sem explicação, poucas linhas)."
)


def _context_block(ctx: AssistantContext) -> str:
    parts: list[str] = []
    if ctx.imports:
        parts.append("# Imports já feitos:\n" + "\n".join(ctx.imports))
    if ctx.defined_names:
        parts.append("# Nomes já definidos: " + ", ".join(ctx.defined_names))
    if ctx.preceding_cells:
        parts.append(
            "# Células anteriores (mais recentes por último):\n\n"
            + "\n\n# ---\n\n".join(ctx.preceding_cells)
        )
    if ctx.workspace_files:
        parts.append("# Arquivos relevantes do workspace:\n" + "\n".join(ctx.workspace_files))
    if ctx.recent_error:
        parts.append("# Erro da última execução:\n" + ctx.recent_error)
    return "\n\n".join(parts)


def build_messages(
    task: AssistantTask,
    ctx: AssistantContext,
    *,
    instruction: str | None = None,
    chat_history: list[ChatMessage] | None = None,
    target_language: str | None = None,
) -> list[ChatMessage]:
    if task is AssistantTask.INLINE:
        prefix = ctx.cursor_prefix or ctx.current_cell
        suffix = ctx.cursor_suffix or ""
        ctxb = _context_block(ctx)
        user = (
            (ctxb + "\n\n" if ctxb else "")
            + "# Código antes do cursor:\n"
            + prefix
            + "\n# <cursor>\n"
            + ("# Código depois do cursor:\n" + suffix if suffix else "")
        )
        return [ChatMessage("system", _INLINE_SYSTEM), ChatMessage("user", user)]

    if task is AssistantTask.CHAT:
        msgs: list[ChatMessage] = [ChatMessage("system", SYSTEM_BASE)]
        ctxb = _context_block(ctx)
        if ctx.current_cell.strip():
            ctxb = (ctxb + "\n\n" if ctxb else "") + "# Célula atual:\n" + ctx.current_cell
        if ctxb:
            msgs.append(ChatMessage("system", "Contexto do notebook:\n\n" + ctxb))
        msgs.extend(chat_history or [])
        if instruction:
            msgs.append(ChatMessage("user", instruction))
        return msgs

    verb = {
        AssistantTask.GENERATE: "Gere o código que atende ao pedido do usuário.",
        AssistantTask.EXPLAIN: "Explique, em português e de forma objetiva, o que o código faz.",
        AssistantTask.FIX: (
            "Analise o erro e o código e devolva o código corrigido (bloco único). "
            "Se faltar um import, inclua-o."
        ),
        AssistantTask.OPTIMIZE: "Reescreva o código com melhorias de performance/clareza, "
        "preservando o comportamento.",
        AssistantTask.TESTS: "Gere testes (pytest) para as funções do código.",
        AssistantTask.CONTINUE: "Continue a implementação da célula atual de forma coerente.",
        AssistantTask.CONVERT: (
            f"Converta o código para {target_language or 'a linguagem pedida'}."
        ),
        AssistantTask.DOCSTRING: "Adicione docstrings e type hints, sem mudar o comportamento.",
    }[task]

    ctxb = _context_block(ctx)
    user = (
        (ctxb + "\n\n" if ctxb else "")
        + "# Célula atual:\n"
        + (ctx.selection or ctx.current_cell)
        + "\n\n"
        + verb
    )
    if instruction:
        user += "\n\n# Pedido do usuário:\n" + instruction
    return [ChatMessage("system", SYSTEM_BASE), ChatMessage("user", user)]
