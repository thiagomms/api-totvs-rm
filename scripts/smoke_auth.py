"""
Smoke test de autenticação na API Ahgora Integrações.

Faz GET /process com Basic Auth (e, se falhar, variações comuns)
para verificar se as credenciais do .env são aceitas, sem enviar
funcionários ou alterações reais.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Garante que o .env na raiz do projeto seja carregado mesmo rodando de outra pasta.
ROOT_DIR = Path(__file__).resolve().parent.parent


def carregar_config() -> tuple[str, str, str]:
    """Lê usuário, senha e URL base do .env e valida se estão preenchidos."""
    load_dotenv(ROOT_DIR / ".env")
    user = (os.getenv("AHGORA_USER") or "").strip()
    password = (os.getenv("AHGORA_PASS") or "").strip()
    base_url = (os.getenv("AHGORA_BASE_URL") or "https://api.ahgora.com.br").rstrip("/")

    if not user or not password:
        raise SystemExit(
            "Credenciais ausentes. Preencha AHGORA_USER e AHGORA_PASS no arquivo .env."
        )
    return user, password, base_url


def montar_url_process(base_url: str, subunique: str = "teste") -> str:
    """Monta a URL do endpoint GET /process com o parâmetro subunique."""
    return f"{base_url}/process?subunique={subunique}"


def interpretar_status(status_code: int) -> str:
    """Explica de forma objetiva o que o status HTTP indica sobre a autenticação."""
    if status_code == 401:
        return "Falha de autenticação (401). Verifique usuário/senha ou formato de auth."
    if status_code == 403:
        return "Autenticado ou reconhecido, mas sem permissão (403)."
    if 200 <= status_code < 300:
        return "Autenticação OK (2xx). Endpoint respondeu com sucesso."
    if status_code == 404:
        return (
            "Provável autenticação OK: 404 no /process costuma indicar "
            "subunique inexistente, não credencial inválida."
        )
    return (
        f"Status {status_code}: se não for 401, a API provavelmente aceitou "
        "a autenticação e rejeitou/processou a consulta por outro motivo."
    )


def _token_basic(user: str, password: str) -> str:
    """Gera o valor Base64 de user:password para o header Authorization Basic."""
    raw = f"{user}:{password}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def listar_variacoes_auth(user: str, password: str) -> list[tuple[str, dict, dict]]:
    """
    Monta variações de autenticação para o smoke.

    Cada item: (nome, kwargs do requests.get, headers extras).
    """
    token = _token_basic(user, password)
    return [
        ("basic", {"auth": (user, password)}, {}),
        ("basic_invertido", {"auth": (password, user)}, {}),
        ("header_basic", {}, {"Authorization": f"Basic {token}"}),
        ("account_password", {}, {"Account": user, "Password": password}),
        ("api_key_secret", {}, {"api-key": user, "api-secret": password}),
        ("x_api_key_secret", {}, {"X-Api-Key": user, "X-Api-Secret": password}),
    ]


def executar_requisicao(
    url: str,
    kwargs: dict,
    headers: dict,
) -> requests.Response:
    """Executa um GET /process com os kwargs/headers informados."""
    return requests.get(url, headers=headers or None, timeout=30, **kwargs)


def executar_smoke(user: str, password: str, base_url: str) -> tuple[str, requests.Response]:
    """
    Tenta autenticação: primeiro Basic Auth; se 401, testa as demais variações.

    Retorna (nome_da_variacao_que_funcionou_ou_ultima, response).
    """
    url = montar_url_process(base_url)
    print(f"GET {url}")
    print("Senha omitida nos logs.")

    ultima_nome = ""
    ultima_response: requests.Response | None = None

    for nome, kwargs, headers in listar_variacoes_auth(user, password):
        print(f"\n--- Tentativa: {nome} ---")
        response = executar_requisicao(url, kwargs, headers)
        print(f"Status HTTP: {response.status_code}")
        print(f"Interpretação: {interpretar_status(response.status_code)}")
        body = (response.text or "").strip()
        if body:
            print(f"Corpo (até 300 chars): {body[:300]}")
        ultima_nome = nome
        ultima_response = response
        if response.status_code != 401:
            return nome, response

    assert ultima_response is not None
    return ultima_nome, ultima_response


def main() -> int:
    """Ponto de entrada: carrega config, executa o smoke e imprime o resultado."""
    user, password, base_url = carregar_config()
    try:
        nome, response = executar_smoke(user, password, base_url)
    except requests.RequestException as exc:
        print(f"Erro de rede/HTTP ao chamar a API: {exc}")
        return 1

    print("\n=== Resumo ===")
    print(f"Última/melhor variação: {nome}")
    print(f"Status HTTP: {response.status_code}")
    print(f"Interpretação: {interpretar_status(response.status_code)}")

    return 1 if response.status_code == 401 else 0


if __name__ == "__main__":
    sys.exit(main())
