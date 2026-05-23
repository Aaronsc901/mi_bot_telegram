import requests

def obtener_numeros_salidos_por_tipo(tipo):
    url = "https://raw.githubusercontent.com/Aaronsc901/animalitos_data/master/resultados_animalitos.json"

    try:
        response = requests.get(url, timeout=5)
        data = response.json()
    except Exception as e:
        print("ERROR al obtener resultados:", e)
        return set()

    numeros = set()
    tipo = tipo.lower()

    try:
        # GUÁCHARO ACTIVO
        if "guacharo" in tipo:
            for hora, numero in data.get("Guacharo activo", {}).items():
                if numero and str(numero).isdigit():
                    numeros.add(numero)

        # LOTTO ACTIVO
        elif "lotto" in tipo:
            for hora, numero in data.get("Lotto activo", {}).items():
                if numero and str(numero).isdigit():
                    numeros.add(numero)

        # LA GRANJITA
        elif "granjita" in tipo:
            for hora, numero in data.get("La Granjita", {}).items():
                if numero and str(numero).isdigit():
                    numeros.add(numero)

        # RULETA ROYAL → AHORA SÍ SE VALIDA
        elif "ruleta" in tipo:
            for hora, numero in data.get("Ruleta Royal", {}).items():
                if numero and str(numero).isdigit():
                    numeros.add(numero)

    except Exception as e:
        print("ERROR procesando resultados:", e)
        return set()

    return numeros
