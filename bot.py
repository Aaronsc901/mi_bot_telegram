import os
import json
import base64
import requests
from datetime import datetime, time
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------

TOKEN = os.getenv("TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_API_URL = "https://api.github.com/repos/Aaronsc901/mi_bot_telegram/contents/datos.json?ref=master"

GRUPO_REAL_ID = -1002793980909
GRUPO_TEST_ID = -5197810505

MODO_TEST = None
MENSAJE_FIJO_ID = None

# Anti‑spam
ULTIMA_ACCION = {}
COOLDOWN = 30

ULTIMA_EJECUCION_GLOBAL = 0
COOLDOWN_GLOBAL = 3

# ---------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------

def md_escape(text: str) -> str:
    especiales = r"_*[]()~`>#+-=|{}"
    for c in especiales:
        text = text.replace(c, f"\\{c}")
    return text

def cargar_json_remoto():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(GITHUB_API_URL, headers=headers).json()
    contenido = base64.b64decode(r["content"]).decode()
    datos = json.loads(contenido)
    datos["_sha"] = r["sha"]
    return datos

def grupo_permitido(chat_id):
    return chat_id == (GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID)

def cargar_modo_test():
    global MODO_TEST
    try:
        datos = cargar_json_remoto()
        MODO_TEST = datos.get("modo_test", False)
    except:
        MODO_TEST = False

def hora_en_rango(hora_actual, inicio_str, fin_str):
    """Compara hora actual con un rango HH:MM."""
    h_inicio = datetime.strptime(inicio_str, "%H:%M").time()
    h_fin = datetime.strptime(fin_str, "%H:%M").time()
    return h_inicio <= hora_actual <= h_fin

# ---------------------------------------------------------
# SELECCIÓN DE LOTERÍA SEGÚN VENTANAS
# ---------------------------------------------------------

def obtener_loteria_activa(datos):
    ahora = datetime.now(ZoneInfo("America/Caracas")).time()

    for loteria in datos["loterias"]:
        for ventana in loteria["ventanas"]:
            if hora_en_rango(ahora, ventana["activar_inicio"], ventana["activar_fin"]):
                return {
                    "visible": loteria["visible"],
                    "rango_inicio": ventana["rango_inicio"],
                    "rango_fin": ventana["rango_fin"],
                    "jugada": ventana["jugada"]
                }

    return None

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
# CALLBACK PRINCIPAL
# ---------------------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MENSAJE_FIJO_ID, ULTIMA_EJECUCION_GLOBAL

    query = update.callback_query
    user_id = query.from_user.id
    ahora_ts = datetime.now().timestamp()

    # Anti‑spam
    if user_id in ULTIMA_ACCION:
        if ahora_ts - ULTIMA_ACCION[user_id] < COOLDOWN:
            await query.answer("⏳ Espera unos segundos antes de consultar de nuevo.", show_alert=True)
            return

    ULTIMA_ACCION[user_id] = ahora_ts

    # Anti doble ejecución
    if ahora_ts - ULTIMA_EJECUCION_GLOBAL < COOLDOWN_GLOBAL:
        await query.answer("⚠️ Procesando… intenta nuevamente en un momento.")
        return

    ULTIMA_EJECUCION_GLOBAL = ahora_ts

    await query.answer()

    if not grupo_permitido(query.message.chat.id):
        return

    datos = cargar_json_remoto()
    loteria = obtener_loteria_activa(datos)

    if not loteria:
        await query.answer("⚠️ No hay jugada disponible en este momento.", show_alert=True)
        return

    ahora = datetime.now(ZoneInfo("America/Caracas"))

    jugada = [md_escape(j) for j in loteria["jugada"]]
    jugada_texto = " \\- ".join([f"*{j}*" for j in jugada]) if jugada else "*Sin jugada cargada*"

    mensaje = (
        "🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{ahora.strftime('%I:%M %p')}`\n\n"
        f"🎯 *Lotería:* *{md_escape(loteria['visible'])}*\n"
        f"🕒 *Sorteo:* `{loteria['rango_inicio']} - {loteria['rango_fin']}`\n\n"
        "🔢 *Jugada del momento:*\n"
        f"{jugada_texto}"
    )

    chat_destino = GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID

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

    msg = await context.bot.send_message(
        chat_destino,
        mensaje,
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
    await update.message.reply_text("Reiniciado. Mensaje fijo limpiado.")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_callback))

    cargar_modo_test()
    app.run_polling()

if __name__ == "__main__":
    main()
