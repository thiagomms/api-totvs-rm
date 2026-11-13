import requests
from datetime import datetime 
import logging
import os
from dotenv import load_dotenv
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

payload = [{
    "cod_interno": "1|005994",
    "inicio": "2026-10-13T08:00",
    "fim": "2026-10-15T18:00",
    "matricula": "1005994",
    "motivo": "AH001",
    "operation": "INS"
}]

def enviar_abono_teste(payload_envio: list):
    USER = os.getenv("AHGORA_USER_HOMOLOG")
    PASSWORD = os.getenv("AHGORA_PASS_HOMOLOG")
    URL = os.getenv("AHGORA_BASE_URL") 
    
    matricula = payload_envio[0].get("matricula")
    logger.info(f"Enviando POST tts para {URL}/absences {matricula})")
    try:
        resposta = requests.post(
            f"{URL}/absences",
            auth=(USER, PASSWORD),
            json=payload_envio, 
            headers={"Content-Type": "application/json"}
        )
        if resposta.status_code == 200:
            dados = resposta.json()
            logger.info(f"Sucesso, protocolo: {dados.get('unique')}")
            return dados
        else:
            logger.error(f"Erro Ahgora HTTP {resposta.status_code}: {resposta.text}")
            return {}
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha de comunicação: {e}")
        return {}

if __name__ == "__main__":
    resultado = enviar_abono_teste(payload)
    print("Resultado do teste:", resultado)