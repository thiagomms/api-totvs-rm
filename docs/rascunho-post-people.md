# Rascunho — POST /people (localizações Sede / Gama)

**Status:** rascunho apenas. **Não enviar** para produção sem aprovação explícita.

## Objetivo

Exemplo mínimo de alteração de colaborador via API Ahgora Integrações, incluindo o campo flexível `localizacoes` com `SEDE` e `GAMA`.

## Endpoint

| Item | Valor |
|------|--------|
| Método | `POST` |
| URL | `https://api.ahgora.com.br/people` |
| Auth | HTTP Basic (`AHGORA_USER` / `AHGORA_PASS`) |
| Content-Type | `application/json` |

## Payload de exemplo

Arquivo: [`exemplos/post-people-localizacoes.json`](exemplos/post-people-localizacoes.json)

```json
[
  {
    "matricula": "0001234",
    "nome": "Colaborador Exemplo",
    "localizacoes": ["SEDE", "GAMA"]
  }
]
```

O corpo é um **array** de funcionários (mesmo para um único registro).

## Campos usados neste rascunho

| Campo | Obrigatório neste rascunho | Observação |
|-------|----------------------------|------------|
| `matricula` | Sim | Chave do colaborador no PontoWeb. Em integrações Totvs costuma ser Empresa+Filial+Matrícula concatenados (sem separador). Ajuste para o formato real do seu tenant. |
| `nome` | Recomendado | Nome completo. |
| `localizacoes` | Sim (foco da demanda) | Array de strings. Campo **flexível**: os valores precisam existir/combinar com o que o PontoWeb/cliente espera. |

## Campos comuns (não incluídos no JSON mínimo)

Úteis em admissão/alteração completa (conforme layout Totvs/Ahgora). Preencher só se for necessário no seu caso:

- `pis`, `sem_pis`, `matricula_esocial`, `cpf`, `rg`
- `dataAdmissao`, `dataDemissao`
- `codInterno` (ex.: `01|001|1234`)
- `cnpj`, `centroCusto`, `cargo`, `departamento`
- `escala_padrao`, `bate_ponto`, `matricula_chefia`

Documentação de referência de layout: [ITG2.0-TN12 (TDN)](https://tdn.totvs.com/display/AHINT/ITG2.0-TN12+Layout+de+campos+Protheus+Nativa+x+Ahgora+PontoWeb).

## Riscos e dúvidas

1. **Códigos `SEDE` / `GAMA`**: são exemplos alinhados à demanda; confirme no PontoWeb se esses literais são os códigos oficiais do tenant (podem ser outros textos/IDs).
2. **Matrícula fictícia `0001234`**: trocar por matrícula real **só** em homologação aprovada.
3. **Alteração parcial**: a API trata envio de funcionários (admissão/alteração/demissão). Antes do POST real, confirme com Ahgora/Totvs se um payload mínimo (só `matricula` + `localizacoes`) é aceito no seu contrato, ou se exige o conjunto completo de campos.
4. **Aparelho físico** (celular Ahgora Multi por unidade): **fora** deste endpoint; ver README do projeto.

## Como testar depois (quando você autorizar)

1. Substituir `matricula` / `nome` por dados de **homologação**.
2. Confirmar códigos de `localizacoes` com o responsável PontoWeb.
3. Enviar com Basic Auth e guardar o `subunique` da resposta (se houver).
4. Consultar status em `GET /process?subunique=...`.

**Não execute POST em produção a partir deste rascunho sem aprovação.**

## Comando curl de referência (não executar sem autorização)

```bash
curl -X POST "https://api.ahgora.com.br/people" \
  -u "$AHGORA_USER:$AHGORA_PASS" \
  -H "Content-Type: application/json" \
  -d @docs/exemplos/post-people-localizacoes.json
```
