import requests
from bs4 import BeautifulSoup
import json
import base64
from datetime import datetime, timedelta
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

def convertir_hora(hora_str):
    try:
        return datetime.strptime(hora_str, "%I:%M %p").time()
    except:
        return None

def scrape_loteria(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []
    vistos = set()
    hoy = datetime.now().date()

    items = soup.find_all("li", class_="step-item")

    for item in items:
        hora_tag = item.find("h4")
        hora = hora_tag.get_text(strip=True) if hora_tag else None

        texto_tag = item.find("p", class_="step-text")
        texto = texto_tag.get_text(strip=True) if texto_tag else None

        if not hora or not texto:
            continue

        hora_24 = convertir_hora(hora)
        if not hora_24:
            continue

        # Convertimos a datetime completo
        fecha_hora = datetime.combine(hoy, hora_24)

        # Filtrar resultados del día anterior
        if fecha_hora.date() != hoy:
            continue

        # Evitar duplicados
        if hora in vistos:
            continue
        vistos.add(hora)

        numero = texto.split(" ", 1)[0]

        resultados.append({
            "hora": hora,
            "hora_24": hora_24.strftime("%H:%M"),
            "numero": numero
        })

    # Ordenar por hora
    resultados.sort(key=lambda x: x["hora_24"])

    return resultados

def subir_a_github(data):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"

    contenido = json.dumps(data, indent=4, ensure_ascii=False)
    contenido_b64 = base64.b64encode(contenido.encode()).decode()

    headers = {
        "Authorization": f"token {TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

    payload = {
        "message": "Actualización automática de resultados animalitos",
        "content": contenido_b64
    }

    if sha:
        payload["sha"] = sha

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
