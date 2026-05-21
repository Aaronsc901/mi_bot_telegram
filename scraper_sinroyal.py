import requests
from bs4 import BeautifulSoup
import json
import base64
from datetime import datetime
import os

GITHUB_USER = "Aaronsc901"
REPO = "animalitos_data"
FILE_PATH = "resultados_animalitos.json"

TOKEN = os.getenv("TOKENX")
if not TOKEN:
    raise Exception("ERROR: La variable de entorno TOKENX no está definida.")

URL_GUACHARO = "https://www.lottoresultados.com/resultados/animalitos/guacharo-activo/"
URL_GRANJITA = "https://www.lottoresultados.com/resultados/animalitos/la-granjita/" 
URL_LOTTO = "https://www.lottoresultados.com/resultados/animalitos/lotto-activo/"

def scrape_loteria(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []

    items = soup.find_all("li", class_="step-item")


    for item in items:
        hora_tag = item.find("h4")
        hora = hora_tag.get_text(strip=True) if hora_tag else None

        texto_tag = item.find("p", class_="step-text")
        texto = texto_tag.get_text(strip=True) if texto_tag else None

        if texto:
            numero = texto.split(" ", 1)[0]

            resultados.append({
                "hora": hora,
                "numero": numero
            })

    return resultados

def subir_a_github(data):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"

    contenido = json.dumps(data, indent=4, ensure_ascii=False)
    contenido_b64 = base64.b64encode(contenido.encode()).decode()

    headers = {
        "Authorization": f"token {TOKEN}",
        "Content-Type": "application/json"
    }

    # 1. Obtener SHA actual (si existe)
    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        sha = r.json().get("sha")
    else:
        sha = None  # Archivo no existe

    # 2. Crear payload
    payload = {
        "message": "Actualización automática de resultados animalitos",
        "content": contenido_b64
    }

    if sha:
        payload["sha"] = sha  # NECESARIO para evitar error 409

    # 3. Subir archivo
    r = requests.put(url, json=payload, headers=headers)

    if r.status_code in [200, 201]:
        print("✔ Archivo actualizado en GitHub")
    else:
        print("❌ Error al subir:", r.text)

if __name__ == "__main__":
    data = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "guacharo_activo": scrape_loteria(URL_GUACHARO),
        "la_granjita": scrape_loteria(URL_GRANJITA),
        "lotto_activo": scrape_loteria(URL_LOTTO)
    }

    subir_a_github(data)
    print("Scraping completado.")
