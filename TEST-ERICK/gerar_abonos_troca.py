"""
Gera os abonos de troca de plantão (Vivi Bot) a partir da planilha exportada
pela query-abono.sql, no formato aceito por scripts/abono_presenca.py --file.

Regra (cada troca gera 2 abonos, um para cada pessoa):
  - Solicitante: abono no dia da "Data da troca" (o substituto cobriu o plantão dele).
  - Substituto:  abono no dia da "Folga"/"Reposição" (o solicitante cobriu o dele).

A mesma troca pode aparecer duas vezes na planilha (uma anotação no solicitante,
formato "Reposição", e outra no substituto, formato "Folga"); a chave
(solicitante, substituto, data da troca) elimina a duplicidade.

Uso:
  python gerar_abonos_troca.py "Pasta1 1.xlsx" --saida abonos.json [--chapa 000932]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import openpyxl

MOTIVO = "AH001"  # AH001 - TROCA ESCALA (código existe só na prod a743861)
CODCOLIGADA = "1"

PADRAO = re.compile(
    r"Solicitante:\s*(?P<sol_nome>.+?)\s*\((?P<sol>\d+)\)\s*com Substituto:\s*"
    r"(?P<sub_nome>.+?)\s*\((?P<sub>\d+)\)\.\s*Data da troca:?\s*(?P<troca>\d{2}/\d{2}/\d{4})\.\s*"
    r"(?:Folga|Reposi\S*):\s*(?P<folga>\d{2}/\d{2}/\d{4})"
)


def iso(data_br: str) -> str:
    """Converte dd/mm/aaaa em aaaa-mm-dd."""
    return datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")


def ler_trocas(planilha: Path) -> tuple[dict, list[str]]:
    """Lê a planilha e devolve as trocas únicas e os textos que não casaram com o padrão."""
    ws = openpyxl.load_workbook(planilha, read_only=True).active
    linhas = ws.iter_rows(min_row=2, values_only=True)
    trocas: dict[tuple[str, str, str], dict] = {}
    invalidos = []
    for linha in linhas:
        texto = linha[4] or ""
        m = PADRAO.search(texto)
        if not m:
            invalidos.append(texto)
            continue
        chave = (m["sol"], m["sub"], iso(m["troca"]))
        trocas.setdefault(chave, {**m.groupdict(), "troca": iso(m["troca"]), "folga": iso(m["folga"])})
    return trocas, invalidos


def montar_abonos(trocas: dict) -> list[dict]:
    """Gera os 2 abonos (solicitante e substituto) de cada troca."""
    abonos = []
    for t in trocas.values():
        sufixo = f"{t['sol']}-{t['sub']}-{t['troca'].replace('-', '')}"
        for papel, chapa, dia in (("sol", t["sol"], t["troca"]), ("sub", t["sub"], t["folga"])):
            abonos.append({
                "matricula": CODCOLIGADA + chapa,
                "inicio": dia,
                "fim": dia,
                "motivo": MOTIVO,
                "operation": "INS",
                "cod_interno": f"troca-{sufixo}-{papel}",
            })
    return abonos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("planilha", type=Path)
    parser.add_argument("--saida", type=Path, default=Path("abonos.json"))
    parser.add_argument("--chapa", help="Só as trocas em que essa chapa participa (para teste).")
    parser.add_argument("--ignorar-chapa", nargs="*", default=[],
                        help="Descarta as trocas em que essas chapas participam (ex.: registros de teste).")
    parser.add_argument("--ja-enviados", nargs="*", type=Path, default=[],
                        help="JSONs já enviados; os cod_interno deles ficam fora do lote.")
    args = parser.parse_args()

    trocas, invalidos = ler_trocas(args.planilha)
    if args.chapa:
        trocas = {k: v for k, v in trocas.items() if args.chapa in (v["sol"], v["sub"])}
    if args.ignorar_chapa:
        trocas = {k: v for k, v in trocas.items()
                  if not {v["sol"], v["sub"]} & set(args.ignorar_chapa)}

    abonos = montar_abonos(trocas)
    if args.ja_enviados:
        enviados = {a["cod_interno"] for f in args.ja_enviados
                    for a in json.loads(f.read_text(encoding="utf-8"))}
        antes = len(abonos)
        abonos = [a for a in abonos if a["cod_interno"] not in enviados]
        print(f"{antes - len(abonos)} abono(s) já enviados removidos do lote.")
    args.saida.write_text(json.dumps(abonos, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(trocas)} troca(s) única(s) -> {len(abonos)} abono(s) em {args.saida}")
    for t in trocas.values():
        print(f"  {t['sol_nome']} ({t['sol']}) abono {t['troca']}  |  "
              f"{t['sub_nome']} ({t['sub']}) abono {t['folga']}")
    if invalidos:
        print(f"\n{len(invalidos)} texto(s) fora do padrão (ignorados):")
        for texto in invalidos:
            print("  ", texto)


if __name__ == "__main__":
    main()
