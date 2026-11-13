"""
Abono de presença/ausência via API Ahgora Integrações (POST /absences).

Suporta um abono individual (via argumentos de linha de comando) ou um lote
(via arquivo JSON com uma lista de abonos). Por padrão roda em modo dry-run
(só mostra o payload que seria enviado); é necessário passar --send para
realmente enviar à API.

Schema oficial (operationId syncAbsences):
https://ahi-core.app.ahgora.com.br/api/docs/#/Absences/syncAbsences

Campos obrigatórios: cod_interno, inicio, fim, matricula, motivo, operation.
Campos opcionais: cid, crm.

O "motivo" precisa ser IDÊNTICO a um motivo de afastamento já cadastrado no
PontoWeb, senão a API rejeita a integração.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from people_test import COMPANIES_PADRAO, Ambiente, carregar_config, company_da_resposta

OPERACOES_VALIDAS = {"INS", "ALT", "DEL"}


@dataclass
class Abono:
    """Um item do payload de POST /absences."""

    matricula: str
    inicio: str
    fim: str
    motivo: str
    operation: str = "INS"
    cod_interno: str = ""
    cid: str = ""
    crm: str = ""

    def validar(self) -> None:
        """Valida campos obrigatórios e regras do endpoint antes do envio."""
        if self.operation not in OPERACOES_VALIDAS:
            raise SystemExit(
                f"operation inválida: {self.operation!r}. Use um de {sorted(OPERACOES_VALIDAS)}."
            )
        if self.operation in {"ALT", "DEL"} and not self.cod_interno:
            raise SystemExit(
                "cod_interno é obrigatório para operation ALT ou DEL "
                "(é a chave que referencia o abono já criado)."
            )
        if not self.cod_interno:
            # A API exige cod_interno mesmo em INS; geramos um automaticamente
            # para não obrigar o usuário a inventar um identificador único.
            self.cod_interno = f"abono-{self.matricula}-{uuid.uuid4().hex[:8]}"
        for campo in ("matricula", "inicio", "fim", "motivo"):
            if not getattr(self, campo):
                raise SystemExit(f"Campo obrigatório ausente: {campo}")

    def payload(self) -> dict:
        """Monta o dict a ser enviado, omitindo campos opcionais vazios."""
        dados = asdict(self)
        return {k: v for k, v in dados.items() if v}


def montar_parser() -> argparse.ArgumentParser:
    """Configura os argumentos de linha de comando do script."""
    parser = argparse.ArgumentParser(
        description="Abona presença/ausência de funcionário(s) via API Ahgora (/absences)."
    )
    parser.add_argument("--matricula", help="Registro do funcionário (abono individual).")
    parser.add_argument("--inicio", help="Início no formato YYYY-MM-DDTHH:mm.")
    parser.add_argument("--fim", help="Fim no formato YYYY-MM-DDTHH:mm.")
    parser.add_argument(
        "--motivo",
        help="Motivo do afastamento. Deve existir cadastrado no PontoWeb com esse nome exato.",
    )
    parser.add_argument(
        "--operation",
        default="INS",
        choices=sorted(OPERACOES_VALIDAS),
        help="INS (inserir, padrão), ALT (alterar) ou DEL (remover).",
    )
    parser.add_argument("--cod-interno", default="", help="Obrigatório para ALT/DEL.")
    parser.add_argument("--cid", default="", help="Código CID do atestado (opcional).")
    parser.add_argument("--crm", default="", help="CRM do médico responsável (opcional).")
    parser.add_argument(
        "--file",
        type=Path,
        help=(
            "Arquivo JSON com uma lista de abonos em lote, cada item com os mesmos "
            "campos aceitos via linha de comando. Ignora --matricula/--inicio/etc."
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


def carregar_lote_do_arquivo(caminho: Path) -> list[Abono]:
    """Lê um arquivo JSON com lista de abonos e converte para objetos Abono."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        raise SystemExit(f"{caminho} deve conter uma lista JSON de abonos.")
    return [Abono(**item) for item in dados]


def montar_abonos(args: argparse.Namespace) -> list[Abono]:
    """Monta a lista de Abono a partir do arquivo em lote ou dos argumentos individuais."""
    if args.file:
        return carregar_lote_do_arquivo(args.file)

    obrigatorios = (args.matricula, args.inicio, args.fim, args.motivo)
    if not all(obrigatorios):
        raise SystemExit(
            "Informe --matricula, --inicio, --fim e --motivo (ou use --file para lote)."
        )
    return [
        Abono(
            matricula=args.matricula,
            inicio=args.inicio,
            fim=args.fim,
            motivo=args.motivo,
            operation=args.operation,
            cod_interno=args.cod_interno,
            cid=args.cid,
            crm=args.crm,
        )
    ]


def enviar(abonos: list[Abono], amb: Ambiente) -> int:
    """Envia o lote de abonos para POST /absences e imprime o resultado."""
    payload = [abono.payload() for abono in abonos]
    url = f"{amb.base_url}/absences"
    print(f"POST {url}  [ambiente={amb.nome}, company esperada={amb.company}]")
    print(f"Enviando {len(payload)} abono(s). Senha omitida nos logs.")

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
            "se o abono foi de fato aplicado."
        )
        return 0

    print("\nFalha no envio. Revise o payload e os motivos cadastrados no PontoWeb.")
    return 1


def main() -> int:
    """Ponto de entrada: monta os abonos, valida e envia (ou só mostra em dry-run)."""
    parser = montar_parser()
    args = parser.parse_args()

    abonos = montar_abonos(args)
    for abono in abonos:
        abono.validar()

    payload = [abono.payload() for abono in abonos]
    print("Payload que seria enviado:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.send:
        print("\nModo dry-run (padrão). Nenhuma requisição foi enviada.")
        print("Use --send para enviar de verdade à API.")
        return 0

    if not args.ambiente:
        raise SystemExit("Informe --ambiente homolog ou --ambiente prod junto com --send.")
    if args.ambiente == "prod" and not args.confirmo_producao:
        raise SystemExit("Envio para produção exige também --confirmo-producao.")
    return enviar(abonos, carregar_config(args.ambiente))


if __name__ == "__main__":
    sys.exit(main())
