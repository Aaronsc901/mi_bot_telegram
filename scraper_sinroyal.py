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

# ---------------------------------------------------------
# CONVERTIR HORA A FORMATO 24H
# ---------------------------------------------------------

def convertir_hora(hora_str):
    try:
        return datetime.strptime(hora_str, "%I:%M %p").time()
    except:
        return None

# ---------------------------------------------------------
# SCRAPER: CAPTURAR RESULTADOS DE AYER (8am–11am)
# ---------------------------------------------------------

def scrape_loteria(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.find_all("li", class_="step-item")

    resultados = []

    # Convertir todos los resultados crudos
    for item in items:
        hora_tag = item.find("h4")
        texto_tag = item.find("p", class_="step-text")

        if not hora_tag or not texto_tag:
            continue

        hora = hora_tag.get_text(strip=True).lower()
        numero = texto_tag.get_text(strip=True).split(" ", 1)[0]

        # Ignorar "Próximo" y "Pendiente"
        if numero.lower() in ["próximo", "pendiente"]:
            continue

        hora_24 = convertir_hora(hora)
        if not hora_24:
            continue

        resultados.append({
            "hora": hora,
            "hora_24": hora_24,
            "numero": numero
        })

    # ORDENAR por hora
    resultados.sort(key=lambda x: x["hora_24"])

    # DETECTAR BLOQUE DE AYER:
    # AYER empieza cuando la hora baja (ej: 7pm → 8am)
    ayer = []
    for i in range(1, len(resultados)):
        if resultados[i]["hora_24"] < resultados[i-1]["hora_24"]:
            ayer = resultados[i:]
            break

    # FILTRAR AYER 8am–11am
    hora_min = datetime.strptime("08:00 AM", "%I:%M %p").time()
    hora_max = datetime.strptime("11:00 AM", "%I:%M %p").time()

    ayer_filtrado = [
        r for r in ayer
        if hora_min <= r["hora_24"] <= hora_max
    ]

    # Tomar exactamente 4 resultados (8am, 9am, 10am, 11am)
    if len(ayer_filtrado) < 4:
        return []

    # Limpiar campos auxiliares
    return [
        {"hora": r["hora"], "numero": r["numero"]}
        for r in ayer_filtrado[:4]
    ]

# ---------------------------------------------------------
# SUBIR A GITHUB
# ---------------------------------------------------------

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
        "message": "Actualización automática de resultados AYER (8–11am)",
        "content": contenido_b64
    }

    if sha:
        payload["sha"] = sha

    requests.put(url
