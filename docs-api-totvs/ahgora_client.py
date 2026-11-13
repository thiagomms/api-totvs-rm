"""
Cliente mínimo da API Ahgora Integrações (https://api.ahgora.com.br),
pensado para ser importado por outro sistema (ex.: Vivi bot).

Diferente dos scripts de linha de comando do projeto, aqui não há prints
nem SystemExit: erros viram exceções e as respostas voltam como dict.

Documentação oficial: https://ahi-core.app.ahgora.com.br/api/docs/#/
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass

import requests

OPERACOES_VALIDAS = {"INS", "ALT", "DEL"}

# Empresa (company) esperada por ambiente; a resposta da API é conferida contra isso.
COMPANIES_PADRAO = {"homolog": "a138066", "prod": "a743861"}


class AhgoraErro(Exception):
    """Falha de validação, rede ou resposta não-200 da API."""


@dataclass
class Abono:
    """Um item do payload de POST /absences (operationId syncAbsences).

    O "motivo" precisa ser IDÊNTICO a um motivo de afastamento já cadastrado
    no PontoWeb, senão a API rejeita a integração.
    Datas no formato YYYY-MM-DDTHH:mm.
    """

    matricula: str
    inicio: str
    fim: str
    motivo: str
    operation: str = "INS"
    cod_interno: str = ""
    cid: str = ""
    crm: str = ""

    def validar(self) -> None:
        """Valida campos obrigatórios e gera cod_interno quando ausente em INS."""
        if self.operation not in OPERACOES_VALIDAS:
            raise AhgoraErro(f"operation inválida: {self.operation!r}.")
        if self.operation in {"ALT", "DEL"} and not self.cod_interno:
            raise AhgoraErro("cod_interno é obrigatório para ALT ou DEL.")
        for campo in ("matricula", "inicio", "fim", "motivo"):
            if not getattr(self, campo):
                raise AhgoraErro(f"Campo obrigatório ausente: {campo}")
        if not self.cod_interno:
            # Guarde este valor: é a chave para alterar/remover o abono depois.
            self.cod_interno = f"abono-{self.matricula}-{uuid.uuid4().hex[:8]}"

    def payload(self) -> dict:
        """Monta o dict a ser enviado, omitindo campos opcionais vazios."""
        return {k: v for k, v in asdict(self).items() if v}


class AhgoraClient:
    """Cliente HTTP (Basic Auth) para os endpoints usados na integração."""

    def __init__(
        self,
        user: str,
        password: str,
        ambiente: str = "homolog",
        base_url: str = "https://api.ahgora.com.br",
        company: str | None = None,
        timeout: int = 30,
    ) -> None:
        if ambiente not in COMPANIES_PADRAO:
            raise AhgoraErro(f"ambiente inválido: {ambiente!r}. Use homolog ou prod.")
        self.ambiente = ambiente
        self.company = company or COMPANIES_PADRAO[ambiente]
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    @classmethod
    def from_env(cls, ambiente: str = "homolog") -> "AhgoraClient":
        """Lê AHGORA_USER_<AMBIENTE>/AHGORA_PASS_<AMBIENTE> das variáveis de ambiente."""
        sufixo = ambiente.upper()
        user = (os.getenv(f"AHGORA_USER_{sufixo}") or "").strip()
        password = (os.getenv(f"AHGORA_PASS_{sufixo}") or "").strip()
        if not user or not password:
            raise AhgoraErro(f"Defina AHGORA_USER_{sufixo} e AHGORA_PASS_{sufixo}.")
        return cls(
            user,
            password,
            ambiente=ambiente,
            base_url=os.getenv("AHGORA_BASE_URL") or "https://api.ahgora.com.br",
            company=os.getenv(f"AHGORA_COMPANY_{sufixo}") or None,
        )

    def _request(self, metodo: str, caminho: str, **kwargs) -> dict:
        """Executa a chamada, confere status e company, e devolve o JSON."""
        url = f"{self.base_url}{caminho}"
        try:
            response = self.session.request(metodo, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise AhgoraErro(f"Erro de rede em {metodo} {caminho}: {exc}") from exc

        if response.status_code != 200:
            raise AhgoraErro(
                f"{metodo} {caminho} retornou {response.status_code}: {response.text[:500]}"
            )
        try:
            corpo = response.json()
        except ValueError:
            corpo = {"raw": response.text}

        company = _company_da_resposta(corpo)
        if company and company != self.company:
            raise AhgoraErro(
                f"Resposta veio da empresa {company}, mas o ambiente {self.ambiente} "
                f"esperava {self.company}. Credenciais trocadas?"
            )
        return corpo

    def registrar_abonos(self, abonos: list[Abono]) -> dict:
        """POST /absences. Processamento é assíncrono: use consultar_processo depois."""
        for abono in abonos:
            abono.validar()
        return self._request("POST", "/absences", json=[a.payload() for a in abonos])

    def enviar_pessoas(self, pessoas: list[dict]) -> dict:
        """POST /people (admissão/alteração/demissão). Corpo é sempre uma lista."""
        return self._request("POST", "/people", json=pessoas)

    def consultar_processo(self, unique: str = "", subunique: str = "") -> dict:
        """GET /process: status do processamento de um envio anterior."""
        params = {k: v for k, v in {"unique": unique, "subunique": subunique}.items() if v}
        if not params:
            raise AhgoraErro("Informe unique ou subunique.")
        return self._request("GET", "/process", params=params)


def _company_da_resposta(corpo: object) -> str:
    """Extrai o campo company da resposta (raiz ou dentro de data)."""
    if not isinstance(corpo, dict):
        return ""
    dados = corpo.get("data")
    aninhado = dados.get("company") if isinstance(dados, dict) else None
    return str(corpo.get("company") or aninhado or "")
