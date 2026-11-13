"""
Smoke de todos os endpoints da API Ahgora Integrações.

Varre os endpoints da documentação oficial com Basic Auth e imprime
status + trecho do corpo. Nos POST envia apenas [] (payload mínimo
inválido) para checar auth/permissão SEM tentar criar dados reais.

Documentação: https://ahi-core.app.ahgora.com.br/api/docs/#/
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv

# Raiz do projeto (pasta acima de scripts/), para achar o .env.
ROOT_DIR = Path(__file__).resolve().parent.parent

# Limite do trecho do corpo impresso no terminal.
MAX_CORPO = 300


@dataclass(frozen=True)
class EndpointSpec:
    """Descreve um endpoint a ser testado no smoke."""

    nome: str
    method: str
    path: str
    # Se True, envia JSON [] no corpo (probe seguro para POST).
    enviar_array_vazio: bool = False
    # Query string opcional (ex.: subunique no /process).
    query: str = ""


def carregar_config() -> tuple[str, str, str]:
    """Lê AHGORA_USER, AHGORA_PASS e AHGORA_BASE_URL do .env."""
    load_dotenv(ROOT_DIR / ".env")
    user = (os.getenv("AHGORA_USER") or "").strip()
    password = (os.getenv("AHGORA_PASS") or "").strip()
    base_url = (os.getenv("AHGORA_BASE_URL") or "https://api.ahgora.com.br").rstrip("/")

    if not user or not password:
        raise SystemExit(
            "Credenciais ausentes. Preencha AHGORA_USER e AHGORA_PASS no arquivo .env."
        )
    return user, password, base_url


def listar_endpoints() -> list[EndpointSpec]:
    """
    Lista os endpoints da doc Ahgora Integrações para o smoke.

    POSTs usam corpo [] de propósito: não devem gravar registro válido;
    o objetivo é só observar 401/403/400/2xx e o formato de erro.
    """
    return [
        EndpointSpec("process", "GET", "/process", query="subunique=teste"),
        EndpointSpec("vacations", "GET", "/vacations"),
        EndpointSpec("people", "POST", "/people", enviar_array_vazio=True),
        EndpointSpec("subsidiaries", "POST", "/subsidiaries", enviar_array_vazio=True),
        EndpointSpec("punches", "POST", "/punches", enviar_array_vazio=True),
        EndpointSpec("absences", "POST", "/absences", enviar_array_vazio=True),
        EndpointSpec("costcenter", "POST", "/costcenter", enviar_array_vazio=True),
        EndpointSpec("users", "POST", "/users", enviar_array_vazio=True),
        EndpointSpec(
            "vacations_anticipate",
            "POST",
            "/vacations/anticipate",
            enviar_array_vazio=True,
        ),
        EndpointSpec(
            "vacations_paymentDate",
            "POST",
            "/vacations/paymentDate",
            enviar_array_vazio=True,
        ),
    ]


def montar_url(base_url: str, path: str, query: str = "") -> str:
    """Monta a URL completa do endpoint, com query string opcional."""
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{query}"
    return url


def interpretar_status(status_code: int, method: str) -> str:
    """Traduz o status HTTP para uma leitura objetiva do smoke."""
    if status_code == 401:
        return "Auth rejeitada (401)."
    if status_code == 403:
        return "Auth reconheceu, mas sem permissão neste endpoint (403)."
    if 200 <= status_code < 300:
        return "Sucesso (2xx). Revisar o corpo se for POST (inesperado no probe)."
    if status_code == 400:
        return (
            "Requisição inválida (400). Em geral auth passou; "
            "payload/parâmetro rejeitado (esperado no probe de POST com [])."
        )
    if status_code == 404:
        return "Não encontrado (404). Auth provavelmente OK; recurso/rota ausente."
    if status_code == 405:
        return "Método não permitido (405)."
    if status_code == 422:
        return "Payload não processável (422). Auth provavelmente OK."
    return f"Status {status_code} no {method}."


def classificar_resultado(status_code: int) -> str:
    """
    Classifica o resultado para o resumo final.

    auth_ok: não é 401 (API tratou a credencial de alguma forma).
    sem_permissao: 403.
    auth_falhou: 401.
    """
    if status_code == 401:
        return "auth_falhou"
    if status_code == 403:
        return "sem_permissao"
    return "auth_ok_ou_probe"


def chamar_endpoint(
    session: requests.Session,
    base_url: str,
    spec: EndpointSpec,
) -> requests.Response:
    """Executa uma chamada HTTP ao endpoint descrito por EndpointSpec."""
    url = montar_url(base_url, spec.path, spec.query)
    headers = {"Accept": "application/json"}
    if spec.enviar_array_vazio:
        headers["Content-Type"] = "application/json"
        return session.request(
            spec.method,
            url,
            json=[],
            headers=headers,
            timeout=30,
        )
    return session.request(spec.method, url, headers=headers, timeout=30)


def imprimir_resultado(spec: EndpointSpec, response: requests.Response) -> None:
    """Imprime no terminal o resultado de uma tentativa de endpoint."""
    print(f"\n--- {spec.method} {spec.path} ({spec.nome}) ---")
    print(f"Status HTTP: {response.status_code}")
    print(f"Interpretação: {interpretar_status(response.status_code, spec.method)}")
    body = (response.text or "").strip()
    if body:
        print(f"Corpo (até {MAX_CORPO} chars): {body[:MAX_CORPO]}")


def executar_smoke(user: str, password: str, base_url: str) -> list[tuple[EndpointSpec, int]]:
    """
    Percorre todos os endpoints e retorna lista (spec, status_code).

    Usa uma Session com Basic Auth para reaproveitar conexão.
    """
    resultados: list[tuple[EndpointSpec, int]] = []
    print(f"Base URL: {base_url}")
    print("Probe seguro: POSTs enviam apenas []. Senha omitida nos logs.")
    print("Doc: https://ahi-core.app.ahgora.com.br/api/docs/#/")

    with requests.Session() as session:
        session.auth = (user, password)
        for spec in listar_endpoints():
            try:
                response = chamar_endpoint(session, base_url, spec)
            except requests.RequestException as exc:
                print(f"\n--- {spec.method} {spec.path} ({spec.nome}) ---")
                print(f"Erro de rede/HTTP: {exc}")
                resultados.append((spec, -1))
                continue
            imprimir_resultado(spec, response)
            resultados.append((spec, response.status_code))

    return resultados


def imprimir_resumo(resultados: list[tuple[EndpointSpec, int]]) -> int:
    """
    Imprime tabela-resumo e retorna código de saída.

    Exit 0 se nenhum 401; exit 1 se houver falha de auth ou erro de rede.
    """
    print("\n=== Resumo ===")
    teve_401 = False
    teve_rede = False

    for spec, status in resultados:
        if status == -1:
            classe = "erro_rede"
            teve_rede = True
            rotulo = "ERRO_REDE"
        else:
            classe = classificar_resultado(status)
            if classe == "auth_falhou":
                teve_401 = True
            rotulo = f"{status} ({classe})"
        print(f"{spec.method:4} {spec.path:28} -> {rotulo}")

    if teve_401:
        print("\nConclusão: pelo menos um endpoint retornou 401 (credencial rejeitada).")
        return 1
    if teve_rede:
        print("\nConclusão: houve erro de rede em alguma chamada.")
        return 1
    print(
        "\nConclusão: nenhum 401. 403 = sem escopo; 400 = auth OK + payload/param inválido "
        "(esperado nos POSTs com [])."
    )
    re


def main() -> int:
    """Ponto de entrada: carrega config, roda o smoke e imprime o resumo."""
    user, password, base_url = carregar_config()
    resultados = executar_smoke(user, password, base_url)
    return imprimir_resumo(resultados)


if __name__ == "__main__":
    sys.exit(main())
