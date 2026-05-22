import requests

def obtener_numeros_salidos_por_tipo(tipo):
    url = "https://raw.githubusercontent.com/Aaronsc901/animalitos_data/master/resultados_animalitos.json"

    try:
        response = requests.get(url, timeout=5)
        data = response.json()
    except Exception as e:
        print("ERROR al obtener resultados:", e)
        return set()  # No bloquea la jugada

    numeros = set()
    tipo = tipo.lower()

    try:
        # Guacharo Activo
        if "guacharo" in tipo:
            for item in data.get("guacharo_activo", []):
                if str(item.get("numero", "")).isdigit():
                    numeros.add(item["numero"])

        # Lotto Activo / La Granjita
        elif "lotto" in tipo or "granjita" in tipo:
            for item in data.get("lotto_activo", []):
                if str(item.get("numero", "")).isdigit():
                    numeros.add(item["numero"])

            for item in data.get("la_granjita", []):
                if str(item.get("numero", "")).isdigit():
                    numeros.add(item["numero"])

        # Ruleta Royal → NO validar
        elif "ruleta" in tipo:
            return set()

    except Exception as e:
        print("ERROR procesando resultados:", e)
        return set()

    return numeros


def validar_jugada(tipo, jugada):
    try:
        numeros_salidos = obtener_numeros_salidos_por_tipo(tipo)
    except Exception as e:
        print("ERROR en validar_jugada:", e)
        return []  # No bloquea la jugada

    if "ruleta" in tipo.lower():
        return []

    try:
        repetidos = [n for n in jugada if n in numeros_salidos]
        return repetidos
    except Exception as e:
        print("ERROR comparando jugada:", e)
        return []
