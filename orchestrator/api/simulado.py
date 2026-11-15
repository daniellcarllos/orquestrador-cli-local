"""Modelo simulado compatível com o Agno: permite testar fluxos e rodar `--simulado` sem chave nem custo.

Gera respostas válidas para o esquema pedido (a partir do JSON Schema do Pydantic) ou usa um
`responder(papel, mensagens, esquema)` fornecido pelos testes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from agno.metrics import MessageMetrics
from agno.models.base import Model
from agno.models.response import ModelResponse


def exemplo_de_schema(schema: dict, defs: dict | None = None) -> Any:
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return exemplo_de_schema(defs[schema["$ref"].split("/")[-1]], defs)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    for chave in ("anyOf", "oneOf"):
        if chave in schema:
            opcoes = [s for s in schema[chave] if s.get("type") != "null"] or schema[chave]
            return exemplo_de_schema(opcoes[0], defs)
    tipo = schema.get("type")
    if tipo == "object":
        props = schema.get("properties", {})
        return {k: exemplo_de_schema(v, defs) for k, v in props.items()}
    if tipo == "array":
        return [exemplo_de_schema(schema.get("items", {"type": "string"}), defs)]
    if tipo == "integer":
        return max(1, schema.get("minimum", 1))
    if tipo == "number":
        return 1.0
    if tipo == "boolean":
        return True
    if tipo == "null":
        return None
    return "simulado"


@dataclass
class _Simulado(Model):
    id: str = "simulado"
    name: str = "Simulado"
    provider: str = "simulado"
    papel: str = ""
    esquema: Any = None
    responder: Optional[Callable[[str, list, Any], str]] = None

    def _resposta(self, messages, response_format):
        esquema = self.esquema if self.esquema is not None else (response_format if isinstance(response_format, type) else None)
        if self.responder is not None:
            texto = self.responder(self.papel, messages, esquema)
        elif esquema is not None:
            texto = json.dumps(exemplo_de_schema(esquema.model_json_schema()), ensure_ascii=False)
        else:
            texto = f"Resposta simulada de {self.papel or 'agente'}."
        entrada = sum(len(str(m.content or "")) for m in messages) // 4 + 1
        saida = len(texto) // 4 + 1
        r = ModelResponse(role="assistant", content=texto)
        r.response_usage = MessageMetrics(input_tokens=entrada, output_tokens=saida, total_tokens=entrada + saida)
        return r

    def invoke(self, messages, assistant_message, response_format=None, tools=None, tool_choice=None,
               run_response=None, compress_tool_results=False):
        return self._resposta(messages, response_format)

    async def ainvoke(self, messages, assistant_message, response_format=None, tools=None, tool_choice=None,
                      run_response=None, compress_tool_results=False):
        return self._resposta(messages, response_format)

    def invoke_stream(self, *a, **k):
        yield self.invoke(*a, **k)

    async def ainvoke_stream(self, *a, **k):
        yield await self.ainvoke(*a, **k)

    def _parse_provider_response(self, response, **kwargs):
        return response

    def _parse_provider_response_delta(self, response):
        return response


class ModeloSimulado:
    """Fábrica passada a `modelos.criar_modelo`: cria um modelo simulado com o id da escolha."""

    def __init__(self, responder: Callable[[str, list, Any], str] | None = None):
        self.responder = responder

    def para(self, escolha, papel: str = "", esquema=None):
        return _Simulado(id=escolha.modelo, provider="simulado", papel=papel, esquema=esquema, responder=self.responder)
