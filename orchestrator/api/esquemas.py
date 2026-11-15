"""Formatos de resposta de cada papel, validados pelo Agno (saída estruturada)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severidade = Literal["critico", "alto", "medio", "baixo", "info"]


class Triagem(BaseModel):
    tipo: Literal["pergunta", "analise", "revisao", "implementacao", "outro"]
    complexidade: Literal["simples", "media", "alta"]
    risco: Literal["baixo", "alto"] = Field(description="alto se envolver segurança, dados sensíveis, produção ou exclusão")
    areas: list[str] = Field(default_factory=list, description="pastas, módulos ou áreas envolvidas", max_length=12)
    justificativa: str = Field(max_length=400)


class Achado(BaseModel):
    arquivo: str
    linha: int | None = None
    severidade: Severidade
    categoria: Literal["seguranca", "bug", "desempenho", "manutencao", "estilo", "teste"]
    descricao: str = Field(max_length=800)
    correcao: str | None = Field(default=None, max_length=1500)


class RevisaoParcial(BaseModel):
    foco: str
    achados: list[Achado] = Field(default_factory=list, max_length=40)
    observacoes: str = Field(default="", max_length=800)


class Revisao(BaseModel):
    resumo: str = Field(max_length=1500)
    achados: list[Achado] = Field(default_factory=list, max_length=60)
    veredito: Literal["aprovar", "aprovar_com_ressalvas", "ajustar"]
    limites: str = Field(default="", description="o que não pôde ser verificado", max_length=800)


class AnaliseModulo(BaseModel):
    area: str
    responsabilidade: str = Field(max_length=800)
    dependencias: list[str] = Field(default_factory=list, max_length=20)
    riscos: list[str] = Field(default_factory=list, max_length=10)


class Analise(BaseModel):
    visao_geral: str = Field(max_length=2500)
    modulos: list[AnaliseModulo] = Field(default_factory=list, max_length=20)
    riscos: list[str] = Field(default_factory=list, max_length=15)
    recomendacoes: list[str] = Field(default_factory=list, max_length=15)


class Subtarefa(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]{1,30}$")
    titulo: str = Field(max_length=200)
    descricao: str = Field(max_length=2000)
    arquivos: list[str] = Field(default_factory=list, max_length=20, description="arquivos que a subtarefa pode alterar")
    criterios_aceite: list[str] = Field(default_factory=list, max_length=10)


class PlanoDesenvolvimento(BaseModel):
    objetivo: str = Field(max_length=1000)
    subtarefas: list[Subtarefa] = Field(min_length=1, max_length=6)
    riscos: list[str] = Field(default_factory=list, max_length=10)


class ArquivoAlterado(BaseModel):
    caminho: str
    conteudo: str = Field(description="conteúdo completo e final do arquivo")


class Implementacao(BaseModel):
    subtarefa: str
    arquivos: list[ArquivoAlterado] = Field(default_factory=list, max_length=20)
    resumo: str = Field(max_length=1500)


class Consolidacao(BaseModel):
    resumo: str = Field(max_length=2500)
    pronto_para_revisao_humana: bool
    pendencias: list[str] = Field(default_factory=list, max_length=15)
