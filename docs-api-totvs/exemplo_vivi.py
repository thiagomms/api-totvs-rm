"""
Exemplo de como o Vivi bot pode chamar a API Ahgora.

A ideia: o bot coleta os dados na conversa (matrícula, período, motivo) e
chama uma função como `solicitar_abono`, que devolve uma mensagem pronta
para responder ao usuário.

Rodar (homologação):
    python exemplo_vivi.py
"""

from __future__ import annotations

from dotenv import load_dotenv

from ahgora_client import Abono, AhgoraClient, AhgoraErro

load_dotenv()

# Crie o cliente uma vez na inicialização do bot e reaproveite.
cliente = AhgoraClient.from_env("homolog")


def solicitar_abono(matricula: str, inicio: str, fim: str, motivo: str) -> str:
    """Handler chamado pelo bot. Retorna o texto de resposta para o usuário."""
    abono = Abono(matricula=matricula, inicio=inicio, fim=fim, motivo=motivo)
    try:
        resposta = cliente.registrar_abonos([abono])
    except AhgoraErro as exc:
        # Logue o detalhe técnico; ao usuário, mensagem simples.
        print(f"[ahgora] {exc}")
        return "Não consegui registrar o abono agora. O RH foi avisado."

    # Guarde abono.cod_interno + o subunique da resposta para consultar/alterar depois.
    print(f"[ahgora] cod_interno={abono.cod_interno} resposta={resposta}")
    return "Abono enviado! Ele é processado em alguns minutos no PontoWeb."


def status_do_envio(subunique: str) -> dict:
    """Consulta se um envio anterior foi processado."""
    return cliente.consultar_processo(subunique=subunique)


if __name__ == "__main__":
    print(
        solicitar_abono(
            matricula="1000000",          # CODCOLIGADA + CHAPA, ex.: 1 + 000000
            inicio="2026-10-06T08:00",
            fim="2026-10-06T18:00",
            motivo="Atestado Médico",     # precisa existir igual no PontoWeb
        )
    )
