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

# ---------------------------------------------------------
# CONVERTIR HORA A FORMATO 24H
# ---------------------------------------------------------

def convertir_hora(hora_str):
    try:
        return datetime.strptime(hora_str, "%I:%M %p").time()
    except:
        return None

# ---------------------------------------------------------
# SCRAPER: SOLO RESULTADOS DEL DÍA (<= hora actual)
# ---------------------------------------------------------

def scrape_loteria(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.find_all("li", class_="step-item")

    resultados = []
    horas_vistas = set()

    hora_actual = datetime.now().time()
    limite_minimo = datetime.strptime("08:00 AM", "%I:%M %p").time()

    for item in items:
        hora_tag = item.find("h4")
        hora = hora_tag.get_text(strip=True).lower() if hora_tag else None

        texto_tag = item.find("p", class_="step-text")
        texto = texto_tag.get_text(strip=True) if texto_tag else None

        if not hora or not texto:
            continue

        numero = texto.split(" ", 1)[0]

        # Ignorar "Próximo" y "Pendiente"
        if numero.lower() in ["próximo", "pendiente"]:
            continue

        # Convertir hora
        hora_24 = convertir_hora(hora)
        if not hora_24:
            continue

        # Filtrar solo horas del día actual
        if not (limite_minimo <= hora_24 <= hora_actual):
            continue

        # Evitar duplicados por hora (día anterior)
        if hora in horas_vistas:
            continue
        horas_vistas.add(hora)

        resultados.append({
            "hora": hora,
            "hora_24": hora_24.strftime("%H:%M"),
            "numero": numero
        })

    # Ordenar por hora
    resultados.sort(key=lambda x: x["hora_24"])

    # Tomar los últimos 5
    resultados = resultados[-5:]

    # Si no hay 5 → devolver vacío
    if len(resultados) < 5:
        return []

    # Eliminar campo auxiliar
    for r in resultados:
        del r["hora_24"]

    return resultados

# ---------------------------------------------------------
# SUBIR A GITHUB
# ---------------------------------------------------------

def subir_a_github(data):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"

    contenido = json.dumps(data, indent=4, ensure_ascii=False)
    contenido_b64 = base64.b64encode(contenido.encode()).decode()

    headers = {
        "Authorization": f"token {TOKEN}",   # ← AQUÍ ESTABA EL ERROR, YA CORREGIDO
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

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

if __name__ == "__main__":
    data = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "guacharo_activo": scrape_loteria(URL_GUACHARO),
        "la_granjita": scrape_loteria(URL_GRANJITA),
        "lotto_activo": scrape_loteria(URL_LOTTO)
    }

    # -------------------------------
    # PRINT PARA VERIFICAR EN RAILWAY
    # -------------------------------
    print("JSON FINAL GENERADO POR EL SCRAPER:")
    print(json.dumps(data, indent=4, ensure_ascii=False))

    subir_a_github(data)
    print("Scraping completado.")
