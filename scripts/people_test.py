"""
Admissão/alteração/demissão de funcionário via API Ahgora Integrações
(POST /people), usada para testar o fluxo "Pessoas / Recebe" configurado
no Integrador 2.0.

Por padrão roda em modo dry-run (só mostra o payload); é necessário passar
--send para realmente enviar à API. Com --send, --ambiente (homolog|prod) é
obrigatório; prod exige ainda --confirmo-producao. Após o envio, o "company"
da resposta é comparado com a empresa esperada do ambiente.

Schema oficial (operationId syncEmployees):
https://ahi-core.app.ahgora.com.br/api/docs/#/People/syncEmployees

Campos obrigatórios: matricula, nome, pis, dataAdmissao, regimeTrabalho.
Há dezenas de campos opcionais (cargo, departamento, localizacoes, etc.) —
para usá-los, monte um arquivo JSON com --file em vez de argumentos
individuais.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
REGIMES_VALIDOS = {
    "clt",
    "estatutario",
    "estagiario",
    "temporario",
    "rda",
    "comissionado",
    "terceirizado",
    "menoraprendiz",
    "intermitente",
    "horista",
    "pensaovitalicia",
    "conselheiro",
    "autonomo",
    "folhaconfidencial",
}


@dataclass
class Employee:
    """Campos obrigatórios + os opcionais mais comuns do schema Employee."""

    matricula: str
    nome: str
    pis: str
    dataAdmissao: str
    regimeTrabalho: str = "clt"
    cargo: str = ""
    departamento: str = ""
    centroCusto: str = ""
    email: str = ""
    cpf: str = ""
    dataNascimento: str = ""

    def validar(self) -> None:
        """Valida campos obrigatórios e o enum de regimeTrabalho."""
        for campo in ("matricula", "nome", "pis", "dataAdmissao"):
            if not getattr(self, campo):
                raise SystemExit(f"Campo obrigatório ausente: {campo}")
        regime = self.regimeTrabalho.lower()
        if regime not in REGIMES_VALIDOS:
            raise SystemExit(
                f"regimeTrabalho inválido: {self.regimeTrabalho!r}. "
                f"Use um de {sorted(REGIMES_VALIDOS)}."
            )
        self.regimeTrabalho = regime

    def payload(self) -> dict:
        """Monta o dict a ser enviado, omitindo campos opcionais vazios."""
        dados = asdict(self)
        return {k: v for k, v in dados.items() if v}


@dataclass
class Ambiente:
    """Credenciais e empresa (company) esperada de um ambiente Ahgora."""

    nome: str
    user: str
    password: str
    base_url: str
    company: str


# Empresa esperada por ambiente (sobrescrevível via AHGORA_COMPANY_<AMBIENTE>).
COMPANIES_PADRAO = {"homolog": "a138066", "prod": "a743861"}


def carregar_config(ambiente: str) -> Ambiente:
    """Lê as credenciais do ambiente no .env.

    homolog: AHGORA_USER_HOMOLOG / AHGORA_PASS_HOMOLOG (sem fallback).
    prod:    AHGORA_USER_PROD / AHGORA_PASS_PROD, ou AHGORA_USER / AHGORA_PASS.
    """
    load_dotenv(ROOT_DIR / ".env")
    sufixo = ambiente.upper()
    user = (os.getenv(f"AHGORA_USER_{sufixo}") or "").strip()
    password = (os.getenv(f"AHGORA_PASS_{sufixo}") or "").strip()
    if ambiente == "prod" and not (user or password):
        user = (os.getenv("AHGORA_USER") or "").strip()
        password = (os.getenv("AHGORA_PASS") or "").strip()
    base_url = (os.getenv("AHGORA_BASE_URL") or "https://api.ahgora.com.br").rstrip("/")
    company = (os.getenv(f"AHGORA_COMPANY_{sufixo}") or COMPANIES_PADRAO[ambiente]).strip()

    if not user or not password:
        raise SystemExit(
            f"Credenciais de {ambiente} ausentes. Preencha AHGORA_USER_{sufixo} e "
            f"AHGORA_PASS_{sufixo} no arquivo .env."
        )
    return Ambiente(ambiente, user, password, base_url, company)


def montar_parser() -> argparse.ArgumentParser:
    """Configura os argumentos de linha de comando do script."""
    parser = argparse.ArgumentParser(
        description="Envia admissão/alteração de funcionário via API Ahgora (/people)."
    )
    parser.add_argument("--matricula", help="Matrícula do funcionário.")
    parser.add_argument("--nome", help="Nome do funcionário.")
    parser.add_argument("--pis", help="PIS/documento trabalhista do funcionário.")
    parser.add_argument("--data-admissao", help="Data de admissão, formato YYYY-MM-DD.")
    parser.add_argument(
        "--regime-trabalho",
        default="clt",
        help=f"Um de: {sorted(REGIMES_VALIDOS)} (padrão: clt).",
    )
    parser.add_argument("--cargo", default="", help="Cargo do funcionário (opcional).")
    parser.add_argument("--departamento", default="", help="Departamento (opcional).")
    parser.add_argument("--centro-custo", default="", help="Código do centro de custo (opcional).")
    parser.add_argument("--email", default="", help="E-mail do funcionário (opcional).")
    parser.add_argument("--cpf", default="", help="CPF do funcionário (opcional).")
    parser.add_argument(
        "--data-nascimento", default="", help="Data de nascimento, formato YYYY-MM-DD (opcional)."
    )
    parser.add_argument(
        "--file",
        type=Path,
        help=(
            "Arquivo JSON com uma lista de funcionários (payload completo, aceita "
            "qualquer campo do schema Employee). Ignora os demais argumentos."
        ),
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Envia de verdade para a API. Sem essa flag, roda em modo dry-run.",
    )
    parser.add_argument(
        "--ambiente",
        choices=sorted(COMPANIES_PADRAO),
        help="Ambiente de destino (obrigatório com --send): homolog ou prod.",
    )
    parser.add_argument(
        "--confirmo-producao",
        action="store_true",
        help="Exigido junto com --ambiente prod --send.",
    )
    return parser


def carregar_lote_do_arquivo(caminho: Path) -> list[dict]:
    """Lê um arquivo JSON com lista de funcionários (payload cru, sem validação de schema)."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        raise SystemExit(f"{caminho} deve conter uma lista JSON de funcionários.")
    return dados


def montar_payload(args: argparse.Namespace) -> list[dict]:
    """Monta a lista de payloads a partir do arquivo em lote ou dos argumentos individuais."""
    if args.file:
        return carregar_lote_do_arquivo(args.file)

    obrigatorios = (args.matricula, args.nome, args.pis, args.data_admissao)
    if not all(obrigatorios):
        raise SystemExit(
            "Informe --matricula, --nome, --pis e --data-admissao (ou use --file para lote)."
        )
    funcionario = Employee(
        matricula=args.matricula,
        nome=args.nome,
        pis=args.pis,
        dataAdmissao=args.data_admissao,
        regimeTrabalho=args.regime_trabalho,
        cargo=args.cargo,
        departamento=args.departamento,
        centroCusto=args.centro_custo,
        email=args.email,
        cpf=args.cpf,
        dataNascimento=args.data_nascimento,
    )
    funcionario.validar()
    return [funcionario.payload()]


def company_da_resposta(response: requests.Response) -> str:
    """Extrai o campo company da resposta JSON (vazio se não houver)."""
    try:
        corpo = response.json()
    except ValueError:
        return ""
    if not isinstance(corpo, dict):
        return ""
    dados = corpo.get("data")
    aninhado = dados.get("company") if isinstance(dados, dict) else None
    return str(corpo.get("company") or aninhado or "")


def enviar(payload: list[dict], amb: Ambiente) -> int:
    """Envia o lote de funcionários para POST /people e imprime o resultado."""
    url = f"{amb.base_url}/people"
    print(f"POST {url}  [ambiente={amb.nome}, company esperada={amb.company}]")
    print(f"Enviando {len(payload)} funcionário(s). Senha omitida nos logs.")

    try:
        response = requests.post(
            url,
            json=payload,
            auth=(amb.user, amb.password),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"Erro de rede/HTTP: {exc}")
        return 1

    print(f"Status HTTP: {response.status_code}")
    print(f"Corpo: {response.text.strip()[:500]}")

    company = company_da_resposta(response)
    if company and company != amb.company:
        print(
            f"\n!!! ATENÇÃO: a resposta veio da empresa {company}, mas o ambiente "
            f"{amb.nome} esperava {amb.company}. Confira no PontoWEB de {company} "
            "e corrija as credenciais no .env."
        )
        return 2
    if not company:
        print(f"\nAviso: resposta sem campo company; não deu para confirmar {amb.company}.")
    else:
        print(f"\nEmpresa confirmada: {company} ({amb.nome}).")

    if response.status_code == 200:
        print(
            "\nSucesso no envio. O processamento é assíncrono: consulte "
            "GET /process?unique=<unique retornado acima> para confirmar "
            "se o funcionário foi de fato processado. Depois confira a aba Logs "
            "do fluxo 'Pessoas' no Integrador 2.0."
        )
        return 0

    print("\nFalha no envio. Revise o payload.")
    return 1


def main() -> int:
    """Ponto de entrada: monta o payload, valida (se aplicável) e envia (ou só mostra)."""
    parser = montar_parser()
    args = parser.parse_args()

    payload = montar_payload(args)
    print("Payload que seria enviado:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.send:
        destino = args.ambiente or "(não informado)"
        print(f"\nModo dry-run (padrão), ambiente: {destino}. Nenhuma requisição foi enviada.")
        print("Use --send --ambiente homolog|prod para enviar de verdade à API.")
        return 0

    if not args.ambiente:
        raise SystemExit("Com --send, informe --ambiente homolog ou --ambiente prod.")
    if args.ambiente == "prod" and not args.confirmo_producao:
        raise SystemExit(
            "Envio para PRODUÇÃO bloqueado. Repita com --confirmo-producao se for intencional."
        )

    amb = carregar_config(args.ambiente)
    return enviar(payload, amb)


if __name__ == "__main__":
    sys.exit(main())
