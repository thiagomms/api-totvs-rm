# Integração Ahgora (PontoWeb) — guia para o Vivi bot

Módulo Python pronto para importar no bot e falar com a API Ahgora Integrações
(`https://api.ahgora.com.br`). Documentação oficial: https://ahi-core.app.ahgora.com.br/api/docs/#/

## Arquivos

| Arquivo | Para quê |
|---------|----------|
| `ahgora_client.py` | Cliente da API. **Este é o arquivo que vai para o bot.** |
| `exemplo_vivi.py` | Exemplo de handler do bot (`solicitar_abono`) usando o cliente. |
| `exemplos/post-absences.json` | Formato do payload de abono (dados fictícios). |
| `exemplos/post-people.json` | Formato do payload de funcionário (dados fictícios). |
| `.env.example` | Variáveis de ambiente necessárias. |
| `requirements.txt` | `requests` e `python-dotenv`. |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # preencher com as credenciais (pedir ao Thiago, não vão por chat)
python exemplo_vivi.py    # testa um abono em HOMOLOGAÇÃO
```

## Uso no bot

```python
from ahgora_client import Abono, AhgoraClient, AhgoraErro

cliente = AhgoraClient.from_env("homolog")   # "prod" só depois de validar

abono = Abono(matricula="1000000", inicio="2026-10-06T08:00",
              fim="2026-10-06T18:00", motivo="Atestado Médico")
try:
    resposta = cliente.registrar_abonos([abono])
except AhgoraErro as exc:
    ...  # responder erro amigável ao usuário e logar exc
```

Métodos disponíveis:

| Método | Endpoint | Uso |
|--------|----------|-----|
| `registrar_abonos(list[Abono])` | `POST /absences` | Abono de ausência (inserir/alterar/remover) |
| `enviar_pessoas(list[dict])` | `POST /people` | Admissão/alteração/demissão de funcionário |
| `consultar_processo(unique=..., subunique=...)` | `GET /process` | Status de um envio anterior |

Toda falha (validação, rede, HTTP ≠ 200, empresa errada) vira `AhgoraErro`.

## Regras que importam

- **Autenticação:** HTTP Basic (usuário/senha da API Integrações, não do PontoWeb).
- **Matrícula** = `CODCOLIGADA` + `CHAPA` do RM. Ex.: coligada `1`, chapa `009587` → `1009587`.
- **Motivo do abono:** prefira o **código** do motivo cadastrado no PontoWeb (ex.: `AH001` = TROCA ESCALA). O nome também é aceito, mas precisa ser idêntico (maiúsculas, acentos, espaços) e falhou para "TROCA ESCALA" mesmo com o texto da lista; pelo código funcionou. O bot deve oferecer uma lista fechada de motivos (código + nome para exibir), nunca texto livre.
- **Datas:** `YYYY-MM-DDTHH:mm` para um período (ex.: `2026-10-15T08:00`). Para o **dia inteiro**, envie só a data (`2026-10-15`) em `inicio` e `fim`: a Ahgora usa o início e o fim da jornada do funcionário.
- **`cod_interno`** é a chave do abono. Se não for informado, o cliente gera um; **o bot deve guardar** esse valor para conseguir alterar (`operation="ALT"`) ou cancelar (`operation="DEL"`) depois.
- **Assíncrono:** o `200` só significa "recebido". Para confirmar que aplicou, consultar `GET /process` com o `subunique`/`unique` da resposta.
- **Corpo sempre é lista**, mesmo com um único item.
- **Ambientes:** `homolog` = empresa `a138066`, `prod` = `a743861`. O cliente confere o `company` da resposta e lança erro se vier de outra empresa (proteção contra credencial trocada).
- **`localizacoes` em `/people`:** texto exato da seção no RM (`PSECAO.DESCRICAO`). A integração nativa RM → Ahgora sobrescreve esse campo a cada reenvio do funcionário.

## Segurança

- Nunca commitar o `.env` nem colar senha em chat/log.
- Começar sempre em `homolog`; trocar para `prod` só com aprovação.
