import requests

def obtener_numeros_salidos_por_tipo(tipo):
    url = "https://raw.githubusercontent.com/Aaronsc901/animalitos_data/master/resultados_animalitos.json"
    data = requests.get(url).json()
    numeros = set()
    tipo = tipo.lower()

    if "guacharo" in tipo:
        for item in data.get("guacharo_activo", []):
            if item["numero"].isdigit():
                numeros.add(item["numero"])

    elif "lotto" in tipo or "granjita" in tipo:
        for item in data.get("lotto_activo", []):
            if item["numero"].isdigit():
                numeros.add(item["numero"])

        for item in data.get("la_granjita", []):
            if item["numero"].isdigit():
                numeros.add(item["numero"])

    elif "ruleta" in tipo:
        return set()

    return numeros


def validar_jugada(tipo, jugada):
    numeros_salidos = obtener_numeros_salidos_por_tipo(tipo)
    if "ruleta" in tipo.lower():
        return []  # sin validación

    repetidos = [n for n in jugada if n in numeros_salidos]
    return repetidos
