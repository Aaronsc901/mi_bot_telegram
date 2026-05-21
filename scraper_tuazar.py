import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

URL_GUACHARO = "https://www.tuazar.com/resultados/animalitos/guacharo-activo/"

def scrape_tuazar(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    resultados = []

    # Cada bloque de sorteo está en filas tipo:
    # "Animalito Guacharo Activo 17 - PAVO 8:00 AM"
    filas = soup.find_all("div", class_="col-12 col-md-6 col-lg-4 mb-3")

    for fila in filas:
        texto = fila.get_text(" ", strip=True)

        # Ejemplo de texto:
        # "Animalito Guacharo Activo 17 - PAVO 8:00 AM"
        partes = texto.split()

        try:
            numero = partes[-3]      # 17
            animal = partes[-2]      # PAVO
            hora = partes[-1]        # 8:00 AM
        except:
            continue

        resultados.append({
            "hora": hora,
            "numero": numero,
            "animal": animal
        })

    return resultados


def guardar_json(data, archivo="resultados_tuazar.json"):
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump({
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "resultados": data
        }, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    data = scrape_tuazar(URL_GUACHARO)
    guardar_json(data)
    print("Scraping completado y guardado en resultados_tuazar.json")
