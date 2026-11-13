"""
Consulta o resultado dos envios de abono de troca (GET /process) e gera uma
planilha separando:
  - Gravados:      abono inserido pela API;
  - Já lançados:   recusado por intersecção (o dia já tinha afastamento/abono);
  - Outros erros:  qualquer outra recusa (revisar);
  - Sem retorno:   enviado mas ainda não processado.

Uso (a partir da pasta TEST-ERICK):
  python relatorio_abonos_troca.py "Pasta1 1.xlsx" --unique 47b69acb bf87683e <unique-do-lote> \
      --enviados abonos-teste-troca-1110.json abonos-teste-outros.json abonos-lote.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import openpyxl
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from people_test import carregar_config  # noqa: E402

from gerar_abonos_troca import ler_trocas, montar_abonos  # noqa: E402

COLUNAS = ["Matrícula", "Chapa", "Nome", "Papel", "Dia do abono", "Troca com",
           "Data da troca", "Folga/Reposição", "cod_interno", "unique", "Cod Ahgora / Mensagem"]


def consultar(unique: str, amb, cache: dict) -> dict:
    """GET /process de um unique (só leitura). O unique expira em poucos dias,
    então cada resposta fica salva no cache e é reaproveitada depois."""
    resp = requests.get(f"{amb.base_url}/process", params={"unique": unique},
                        auth=(amb.user, amb.password), timeout=30)
    if resp.status_code == 200:
        cache[unique] = resp.json()
    elif unique in cache:
        print(f"{unique}: expirado na API, usando o cache local")
    else:
        print(f"{unique}: HTTP {resp.status_code} {resp.text[:150]} (sem cache)")
    return cache.get(unique, {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("planilha", type=Path)
    parser.add_argument("--unique", nargs="+", required=True)
    parser.add_argument("--enviados", nargs="+", type=Path, required=True)
    parser.add_argument("--saida", type=Path, default=Path("relatorio-abonos-troca.xlsx"))
    parser.add_argument("--cache", type=Path, default=Path("process-cache.json"),
                        help="Respostas do /process já obtidas (o unique expira na API).")
    args = parser.parse_args()

    # cod_interno -> dados da troca, para dar nome às linhas do relatório
    trocas, _ = ler_trocas(args.planilha)
    info = {}
    for t in trocas.values():
        sufixo = f"{t['sol']}-{t['sub']}-{t['troca'].replace('-', '')}"
        info[f"troca-{sufixo}-sol"] = (t["sol"], t["sol_nome"], "Solicitante", t["troca"], t["sub_nome"], t)
        info[f"troca-{sufixo}-sub"] = (t["sub"], t["sub_nome"], "Substituto", t["folga"], t["sol_nome"], t)

    enviados = {a["cod_interno"]: a for f in args.enviados
                for a in json.loads(f.read_text(encoding="utf-8"))}

    amb = carregar_config("prod")
    cache = json.loads(args.cache.read_text(encoding="utf-8")) if args.cache.exists() else {}
    resultado: dict[str, tuple[str, str, str]] = {}  # cod_interno -> (grupo, unique, detalhe)
    for unique in args.unique:
        dados = consultar(unique, amb, cache)
        prog = dados.get("progress", {})
        print(f"{unique}: {prog.get('done')}/{prog.get('total')} processados")
        for s in dados.get("data", {}).get("successes", []):
            resultado[s["cod_interno"]] = ("Gravados", unique, str(s.get("cod")))
        for e in dados.get("data", {}).get("errors", []):
            grupo = "Já lançados" if "intersecção" in e["message"] else "Outros erros"
            resultado.setdefault(e["register"], (grupo, unique, e["message"]))
    args.cache.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    abas = {g: wb.create_sheet(g) for g in ("Gravados", "Já lançados", "Outros erros", "Sem retorno")}
    for ws in abas.values():
        ws.append(COLUNAS)

    for cod, abono in enviados.items():
        grupo, unique, detalhe = resultado.get(cod, ("Sem retorno", "", ""))
        chapa, nome, papel, dia, outro, t = info.get(cod, ("", "", "", abono["inicio"], "", {}))
        abas[grupo].append([abono["matricula"], chapa, nome, papel, dia, outro,
                            t.get("troca", ""), t.get("folga", ""), cod, unique, detalhe])

    for ws in abas.values():
        for col, largura in zip("ABCDEFGHIJK", (11, 9, 42, 12, 13, 42, 13, 15, 38, 10, 60)):
            ws.column_dimensions[col].width = largura
        ws.freeze_panes = "A2"
    wb.save(args.saida)

    print(f"\nRelatório: {args.saida}")
    for g, ws in abas.items():
        print(f"  {g}: {ws.max_row - 1}")


if __name__ == "__main__":
    main()
