from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import requests

TOKEN = os.getenv("TOKEN")

# -------------------------------
# CONFIGURACIÓN DE GRUPOS
# -------------------------------

MODO_TEST = True  # Cambia a False cuando quieras usar el grupo real

GRUPO_REAL_ID = -1002793980909          
GRUPO_TEST_ID = -5197810505          

def grupo_permitido(chat_id):
    if MODO_TEST:
        return chat_id == GRUPO_TEST_ID
    return chat_id == GRUPO_REAL_ID

# URL RAW del JSON
URL_DATOS = "https://raw.githubusercontent.com/Aaronsc901/mi_bot_telegram/master/datos.json"

# Variable global para mantener un solo mensaje
MENSAJE_FIJO_ID = None


# -------------------------------
# Funciones utilitarias
# -------------------------------

def obtener_numeros_salidos_por_tipo(tipo):
    url = "https://raw.githubusercontent.com/Aaronsc901/animalitos_data/master/resultados_animalitos.json"
    data = requests.get(url).json()
    numeros = set()
    tipo = tipo.lower()

    # Guacharo Activo
    if "guacharo" in tipo:
        for item in data.get("guacharo_activo", []):
            num = item["numero"]
            if num.isdigit():
                numeros.add(num)

    # Lotto Activo / La Granjita
    elif "lotto" in tipo or "granjita" in tipo:
        for item in data.get("lotto_activo", []):
            num = item["numero"]
            if num.isdigit():
                numeros.add(num)

        for item in data.get("la_granjita", []):
            num = item["numero"]
            if num.isdigit():
                numeros.add(num)

    # Ruleta Royal → NO validar
    elif "ruleta" in tipo:
        return set()

    return numeros


def md_escape(text: str) -> str:
    especiales = r"_*[]()~`>#+-=|{}.!"
    for c in especiales:
        text = text.replace(c, f"\\{c}")
    return text

from time import time
CACHE = {"data": None, "timestamp": 0}

def obtener_datos():
    ahora = time()
    if CACHE["data"] and ahora - CACHE["timestamp"] < 30:
        return CACHE["data"]

    response = requests.get(URL_DATOS)
    CACHE["data"] = response.json()
    CACHE["timestamp"] = ahora
    return CACHE["data"]


# -------------------------------
# Comando /start
# -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_PERMITIDO:
        return

    keyboard = [[InlineKeyboardButton("CONSULTAR JUGADA", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Presiona el botón para ver la jugada actual:",
        reply_markup=reply_markup
    )


# -------------------------------
# Callback del botón
# -------------------------------
#from validacion import validar_jugada
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from validacion import validar_jugada

def calcular_margen(hora_tope_str, intervalo):
    ahora = datetime.now(ZoneInfo("America/Caracas"))

    if intervalo == "60":
        # Próxima hora exacta
        margen_inicio = (
            ahora.replace(minute=0, second=0, microsecond=0)
            + timedelta(hours=1)
        )

    elif intervalo == "30":
        minuto = ahora.minute

        if minuto <= 30:
            # Próxima :30 de esta misma hora
            margen_inicio = ahora.replace(minute=30, second=0, microsecond=0)
        else:
            # Próxima :30 de la siguiente hora
            siguiente_hora = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            margen_inicio = siguiente_hora.replace(minute=30)

    # Hora tope desde el JSON (24h)
    hora_tope = datetime.strptime(hora_tope_str, "%H:%M").time()
    margen_final = datetime.combine(ahora.date(), hora_tope)

    return (
        margen_inicio.strftime("%I:%M %p"),
        margen_final.strftime("%I:%M %p")
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MENSAJE_FIJO_ID
    query = update.callback_query

    if query.message.chat.id != GRUPO_PERMITIDO:
        await query.answer("Este bot solo funciona en el grupo autorizado.")
        return

    await query.answer()

    # Leer datos desde GitHub
    datos = obtener_datos()
    loteria = md_escape(datos["loteria"])
    favorito = md_escape(datos["favorito"])
    jugada = [md_escape(str(j)) for j in datos["jugada"]]
    hora = datetime.now(ZoneInfo("America/Caracas")).strftime("%I:%M %p")
    # Calcular margen dinámico
    margen_inicio, margen_final = calcular_margen(datos["hora_tope"], str(datos["intervalo"]))
    # Calculamos que tal todo
    #tipo = datos["loteria"]
    #jugada_numeros = [str(j) for j in datos["jugada"]]
    #repetidos = validar_jugada(tipo, jugada_numeros)
    #if repetidos:
     #   await query.answer(
      #      f"⚠️ No se puede enviar la jugada.\nEstos números ya salieron hoy: {', '.join(repetidos)}",show_alert=True
       # )
        #return

    # Si ambas horas son iguales, mostrar solo una
    if margen_inicio == margen_final:
        sorteo_texto = f"`{margen_inicio}`"
    else:
        sorteo_texto = f"`{margen_inicio} - {margen_final}`"

    # Construir jugada dinámica con MarkdownV2
    jugada_texto = " \\- ".join([f"*{j}*" for j in jugada])


    mensaje = (
        "🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{hora}`\n\n"
        f"🎯 *Lotería:* *{loteria}*\n"
        f"🕒 *Sorteo:* {sorteo_texto}\n"
        f"🐾 *Favorito:* *{favorito}*\n\n"
        "🔢 *Jugada del momento:*\n"
        f"{jugada_texto}"
    )

    # Intentar editar el mensaje fijo
    if MENSAJE_FIJO_ID:
        try:
            await context.bot.edit_message_text(
                chat_id=GRUPO_PERMITIDO,
                message_id=MENSAJE_FIJO_ID,
                text=mensaje,
                parse_mode="MarkdownV2"
            )
            return
        except Exception as e:
            print("Error al editar:", e)
            MENSAJE_FIJO_ID = None

    # Crear mensaje nuevo
    msg = await context.bot.send_message(
        chat_id=GRUPO_PERMITIDO,
        text=mensaje,
        parse_mode="MarkdownV2"
    )

    MENSAJE_FIJO_ID = msg.message_id

# -------------------------------
# Comando /id (opcional)
# -------------------------------
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MENSAJE_FIJO_ID
    MENSAJE_FIJO_ID = None
    await update.message.reply_text("ID reiniciado. El próximo mensaje será nuevo.")

# -------------------------------
# MAIN
# -------------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))  # opcional
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()


if __name__ == "__main__":
    main()
