# API Totvs / Ahgora Integrações

Projeto mínimo para validar acesso à API Ahgora (`https://api.ahgora.com.br`).

Documentação: https://ahi-core.app.ahgora.com.br/api/docs/#/

## Configuração

1. Copie `.env.example` para `.env` e preencha usuário/senha da API.
2. Instale dependências:

```bash
pip install -r requirements.txt
```

3. Rode o smoke de autenticação:

```bash
python scripts/smoke_auth.py
```

4. (Opcional) Probe de todos os endpoints da [doc](https://ahi-core.app.ahgora.com.br/api/docs/#/) — POSTs com `[]` apenas (sem dados reais):

```bash
python scripts/smoke_endpoints.py
```

5. Abono de presença/ausência (`POST /absences`) — roda em dry-run por padrão:

```bash
# individual
python scripts/abono_presenca.py --matricula 00001234 --inicio 2026-09-11T08:00 \
  --fim 2026-09-11T18:00 --motivo "Atestado Médico"

# em lote (arquivo JSON com lista de abonos, mesmos campos)
python scripts/abono_presenca.py --file lote.json

# só envia de verdade com --send (ambiente obrigatório; prod exige --confirmo-producao)
python scripts/abono_presenca.py --matricula 00001234 --inicio 2026-09-11T08:00 \
  --fim 2026-09-11T18:00 --motivo "Atestado Médico" --send --ambiente homolog
```

O `motivo` precisa ser idêntico a um motivo de afastamento já cadastrado no PontoWeb.

6. Funcionários (`POST /people`) — dry-run por padrão; com `--send` o ambiente é obrigatório:

```bash
python scripts/people_test.py --file docs/exemplos/post-people-teste-009587.json                       # dry-run
python scripts/people_test.py --file docs/exemplos/post-people-teste-009587.json --send --ambiente homolog
python scripts/people_test.py --file ... --send --ambiente prod --confirmo-producao                      # produção
```

Credenciais por ambiente no `.env`:

| Ambiente | Empresa esperada | Variáveis |
|----------|------------------|-----------|
| `homolog` | `a138066` (Homologação) | `AHGORA_USER_HOMOLOG`, `AHGORA_PASS_HOMOLOG` |
| `prod` | `a743861` (Produção) | `AHGORA_USER_PROD`/`AHGORA_PASS_PROD`, ou `AHGORA_USER`/`AHGORA_PASS` |

Após o envio, o `company` da resposta é comparado com a empresa esperada (sobrescrevível via `AHGORA_COMPANY_HOMOLOG` / `AHGORA_COMPANY_PROD`); se não bater, o script avisa e sai com código 2.

**Localizações:** o valor em `localizacoes` é o texto exato do combo do PontoWEB, igual à descrição da seção no RM (`PSECAO.DESCRICAO`), incluindo espaços duplos. A integração nativa do RM envia `localizacoes: [seção]` a cada reenvio do funcionário e sobrescreve o que foi alterado pela API. A matrícula na Ahgora é `CODCOLIGADA` + `CHAPA` (ex.: `1009587`).

## O que esta API permite

| Endpoint | Uso |
|----------|-----|
| `POST /people` | Admissão, alteração e demissão de funcionários (inclui campo `localizacoes`) |
| `POST /subsidiaries` | Cadastro/envio de filiais |
| `POST /punches` | Registro de marcações de ponto |
| `POST /absences` | Ausências |
| `POST /costcenter` | Centros de custo |
| `POST /users` | Usuários |
| `GET /vacations` | Consulta de férias |
| `GET /process` | Status de processo por `subunique` |

Autenticação: **HTTP Basic Auth** (usuário e senha no header `Authorization`).

## O que esta API NÃO permite

- **Não há endpoint** para cadastrar, alterar ou sincronizar **celulares / aparelhos** (ex.: Ahgora Multi) por localização (Sede vs Gama).
- Gestão de aparelhos físicos costuma ser feita no **PontoWEB** (chave de ativação) ou via suporte Ahgora.

## Demanda Sede / Gama — caminhos possíveis

1. **Localização do colaborador** (via API): usar `localizacoes` em `POST /people`, por exemplo:

```json
{
  "matricula": "0001234",
  "nome": "Exemplo",
  "localizacoes": ["SEDE", "GAMA"]
}
```

Não envie este payload em produção sem aprovação explícita.

2. **Aparelho físico em outra unidade**: cadastro/ativação no PontoWEB + suporte Ahgora (fora desta API).

## Segurança

- Nunca commite o arquivo `.env`.
- Não cole senhas em README ou chats compartilhados.
- Se a senha vazou em histórico, peça rotação ao fornecedor.

## Resultado do smoke

Executado em **2026-07-30** via `python scripts/smoke_auth.py`.

| Variação | Status |
|----------|--------|
| `basic` (requests auth) | **401** Unauthorized |
| `basic_invertido` | **401** |
| `header_basic` (Authorization manual) | **401** |
| `account_password` | **401** |
| `api_key_secret` | **401** |
| `x_api_key_secret` | **401** |

**Interpretação:** as credenciais atuais **não foram aceitas** pela API em nenhum formato testado. Próximos cheques com o fornecedor/Ahgora:

1. Confirmar se usuário/senha são mesmo da **API Integrações** (`api.ahgora.com.br`), e não de outro portal.
2. Confirmar se a conta já está **habilitada/liberada** para o tenant (empresa).
3. Verificar se há **allowlist de IP** ou ambiente (homolog vs prod) diferente.
4. Se a senha foi exposta em chat, pedir **rotação** e atualizar o `.env`.

Enquanto o smoke não passar de 401, **não** enviar `POST /people` nem outros payloads.

## Próximo passo (após auth OK)

Escolher um caminho e confirmar antes de qualquer POST real:

- **A — Localização do colaborador (API):** montar exemplo de `POST /people` com `"localizacoes": ["SEDE", "GAMA"]` (só rascunho/homolog até aprovação).
- **B — Aparelho físico Sede/Gama:** cadastro/ativação no **PontoWEB** + suporte Ahgora (esta API **não** gerencia celulares/aparelhos).
