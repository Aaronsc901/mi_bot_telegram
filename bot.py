import os
import json
import base64
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from validacion import validar_jugada

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------

TOKEN = os.getenv("TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# URL API del archivo JSON
GITHUB_API_URL = "https://api.github.com/repos/Aaronsc901/mi_bot_telegram/contents/datos.json"

# Modo test / real
MODO_TEST = True
GRUPO_REAL_ID = -1002793980909
GRUPO_TEST_ID = -5197810505

def grupo_permitido(chat_id):
    return chat_id == (GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID)

# Variables en memoria
MENSAJE_FIJO_ID = None
CACHE = {"data": None, "timestamp": 0}


# ---------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------

def md_escape(text: str) -> str:
    especiales = r"_*[]()~`>#+-=|{}.!"
    for c in especiales:
        text = text.replace(c, f"\\{c}")
    return text


# ---------------------------------------------------------
# LECTURA DEL JSON REMOTO (GitHub)
# ---------------------------------------------------------

def obtener_datos():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(GITHUB_API_URL, headers=headers).json()

    contenido = base64.b64decode(r["content"]).decode()
    datos = json.loads(contenido)

    datos["_sha"] = r["sha"]  # Guardamos el SHA para poder escribir luego
    return datos


# ---------------------------------------------------------
# ESCRITURA DEL JSON REMOTO (GitHub)
# ---------------------------------------------------------

def guardar_datos(datos):
    sha = datos.pop("_sha")  # SHA actual del archivo

    nuevo_contenido = base64.b64encode(
        json.dumps(datos, indent=2).encode()
    ).decode()

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    payload = {
        "message": "Actualización automática del margen opcional",
        "content": nuevo_contenido,
        "sha": sha
    }

    requests.put(GITHUB_API_URL, headers=headers, json=payload)


# ---------------------------------------------------------
# CÁLCULO DE MARGEN PRINCIPAL
# ---------------------------------------------------------

def calcular_margen(hora_tope_str, intervalo):
    ahora = datetime.now(ZoneInfo("America/Caracas"))

    if intervalo == "60":
        margen_inicio = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    elif intervalo == "30":
        minuto = ahora.minute
        if minuto <= 30:
            margen_inicio = ahora.replace(minute=30, second=0, microsecond=0)
        else:
            siguiente_hora = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            margen_inicio = siguiente_hora.replace(minute=30)

    hora_tope = datetime.strptime(hora_tope_str, "%H:%M").time()
    margen_final = datetime.combine(ahora.date(), hora_tope)

    return (
        margen_inicio.strftime("%I:%M %p"),
        margen_final.strftime("%I:%M %p")
    )


# ---------------------------------------------------------
# COMANDO /start
# ---------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not grupo_permitido(update.effective_chat.id):
        return

    keyboard = [[InlineKeyboardButton("CONSULTAR JUGADA", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Presiona el botón para ver la jugada actual:",
        reply_markup=reply_markup
    )


# ---------------------------------------------------------
# CALLBACK DEL BOTÓN
# ---------------------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MENSAJE_FIJO_ID

    query = update.callback_query
    await query.answer()

    if not grupo_permitido(query.message.chat.id):
        return

    datos = obtener_datos()

    # Datos principales
    loteria_tecnica = datos["loteria"]
    loteria_visible = datos.get("loteria_visible", datos["loteria"])

    loteria = md_escape(loteria_visible)
    favorito = md_escape(datos["favorito"])
    jugada = [md_escape(str(j)) for j in datos["jugada"]]
    jugada_numeros = [str(j) for j in datos["jugada"]]

    # Validación principal
    if datos.get("validar_ambas", False):
        from validacion import validar_ambas_loterias
        repetidos = validar_ambas_loterias(jugada_numeros)
    else:
        repetidos = validar_jugada(loteria_tecnica, jugada_numeros)

    # Margen principal
    margen_inicio, margen_final = calcular_margen(datos["hora_tope"], str(datos["intervalo"]))

    ahora = datetime.now(ZoneInfo("America/Caracas"))
    margen_final_dt = datetime.strptime(margen_final, "%I:%M %p").replace(
        year=ahora.year, month=ahora.month, day=ahora.day, tzinfo=ZoneInfo("America/Caracas")
    )

    falta = margen_final_dt - ahora
    activar_por_tiempo = falta.total_seconds() <= 3600

    usar_opcional = False

    # Activación por repetidos
    if repetidos:
        usar_opcional = True

    # Activación por tiempo
    if activar_por_tiempo:
        usar_opcional = True

    # Activación por persistencia
    margen_guardado = datos.get("margen_opcional_activado", None)
    if margen_guardado:
        activado_dt = datetime.fromisoformat(margen_guardado)
        if ahora <= activado_dt + timedelta(hours=5):
            usar_opcional = True
        else:
            datos["margen_opcional_activado"] = None
            guardar_datos(datos)

    # Si debemos usar la jugada opcional
    if usar_opcional:
        jugada_opcional = datos.get("jugada_opcional", [])
        loteria_opcional_tecnica = datos.get("loteria_opcional", None)
        loteria_opcional_visible = datos.get("loteria_opcional_visible", loteria_opcional_tecnica)

        if jugada_opcional and loteria_opcional_tecnica:

            # Validación opcional
            if datos.get("validar_ambas", False):
                from validacion import validar_ambas_loterias
                repetidos_opcional = validar_ambas_loterias(jugada_opcional)
            else:
                repetidos_opcional = validar_jugada(loteria_opcional_tecnica, jugada_opcional)

            if not repetidos_opcional:

                # Activar persistencia si no estaba activa
                if not datos.get("margen_opcional_activado"):
                    datos["margen_opcional_activado"] = ahora.isoformat()
                    guardar_datos(datos)

                activado_dt = datetime.fromisoformat(datos["margen_opcional_activado"])
                margen_inicio = activado_dt.strftime("%I:%M %p")
                margen_final = (activado_dt + timedelta(hours=5)).strftime("%I:%M %p")

                jugada = [md_escape(str(j)) for j in jugada_opcional]
                loteria = md_escape(loteria_opcional_visible)

            else:
                await query.answer(
                    f"❌ No se puede enviar ninguna jugada.\n"
                    f"Principal repetida: {', '.join(repetidos)}\n"
                    f"Opcional repetida: {', '.join(repetidos_opcional)}",
                    show_alert=True
                )
                return

    # Construcción del mensaje
    jugada_texto = " \\- ".join([f"*{j}*" for j in jugada])

    mensaje = (
        "🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{ahora.strftime('%I:%M %p')}`\n\n"
        f"🎯 *Lotería:* *{loteria}*\n"
        f"🕒 *Sorteo:* `{margen_inicio} - {margen_final}`\n"
        f"🐾 *Favorito:* *{favorito}*\n\n"
        "🔢 *Jugada del momento:*\n"
        f"{jugada_texto}"
    )

    chat_destino = GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID

    # Editar mensaje fijo
    if MENSAJE_FIJO_ID:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_destino,
                message_id=MENSAJE_FIJO_ID,
                text=mensaje,
                parse_mode="MarkdownV2"
            )
            return
        except:
            MENSAJE_FIJO_ID = None

    # Crear mensaje nuevo
    msg = await context.bot.send_message(
        chat_id=chat_destino,
        text=mensaje,
        parse_mode="MarkdownV2"
    )

    MENSAJE_FIJO_ID = msg.message_id


# ---------------------------------------------------------
# COMANDOS /id y /reset
# ---------------------------------------------------------

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MENSAJE_FIJO_ID
    MENSAJE_FIJO_ID = None

    datos = obtener_datos()
    datos["margen_opcional_activado"] = None
    guardar_datos(datos)

    await update.message.reply_text("Reiniciado. El próximo mensaje será nuevo.")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()


if __name__ == "__main__":
    main()
