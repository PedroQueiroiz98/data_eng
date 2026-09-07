"""Camada de inteligência do editor (LSP-like) sobre Jedi.

Stateless por request: monta um módulo Python virtual a partir das células do
notebook, roda o Jedi e mapeia posições de volta para (célula, linha, coluna).
Nunca executa código do usuário. É uma camada adicional — se cair, o editor e a
execução via Papermill continuam funcionando.
"""

from nbplatform.services.lsp.service import LspService

__all__ = ["LspService"]
