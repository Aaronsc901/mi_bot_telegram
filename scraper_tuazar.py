import requests
from bs4 import BeautifulSoup
import json
import base64
from datetime import datetime
import os

# -----------------------------------------
# CONFIGURACIÓN
# -----------------------------------------

GITHUB_USER = "Aaronsc901"
REPO = "mi_bot_telegram"
FILE_PATH = "resultados_tuazar.json"

# Token seguro desde variable de entorno
TOKEN = os.getenv("TOKENX")

if not TOKEN:
    raise Exception("ERROR: La variable de entorno GITHUB_TOKEN no está definida.")

URL_GUACHARO = "https://www.tuazar.com/resultados/animalitos/guacharo-activo/"

# -----------------------------------------
# SCRAPING DE TUAZAR
# -----------------------------------------

def scrape_tuazar(url):
    response = requests.get(url, timeout=10)
    print("HTML recibido:", response.text[:500])

    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []

    filas = soup.find_all("div", class_="col-12 col-md-6 col-lg-4 mb-3")

    for fila in filas:
        texto = fila.get_text(" ", strip=True)
        partes = texto.split()

        try:
            numero = partes[-3]
            animal = partes[-2]
            hora = partes[-1]
        except:
            continue

        resultados.append({
            "hora": hora,
            "numero": numero,
            "animal": animal
        })

    return resultados

# -----------------------------------------
# SUBIR ARCHIVO A GITHUB
# -----------------------------------------

def subir_a_github(data):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"

    contenido = json.dumps(data, indent=4, ensure_ascii=False)
    contenido_b64 = base64.b64encode(contenido.encode()).decode()

    headers = {
        "Authorization": f"token {TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        sha = r.json()["sha"]
    else:
        sha = None

    payload = {
        "message": "Actualización automática de resultados TuAzar",
        "content": contenido_b64
    }

    if sha:
        payload["sha"] = sha

    r = requests.put(url, json=payload, headers=headers)

    if r.status_code in [200, 201]:
        print("✔ Archivo actualizado en GitHub")
    else:
        print("❌ Error al subir:", r.text)

# -----------------------------------------
# MAIN
# -----------------------------------------

if __name__ == "__main__":
    resultados = scrape_tuazar(URL_GUACHARO)

    data = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "resultados": resultados
    }

    subir_a_github(data)
    print("Scraping completado.")
