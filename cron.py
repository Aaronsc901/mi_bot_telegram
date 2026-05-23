import json
import os
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

TOKEN = os.getenv("TOKEN")  # Token del bot de Telegram

# CONFIGURACIÓN DE GITHUB
GITHUB_USER = "Aaronsc901"
REPO = "animalitos_data"
FILE_PATH = "resultados_animalitos.json"
GITHUB_TOKEN = os.getenv("TOKENX")  # Token de GitHub

# Estados de la conversación
CHOOSING, LOTERIA, NUMERO, HORA = range(4)

# Loterías disponibles
LOTERIAS = ["Guacharo activo", "Lotto activo", "La Granjita", "Ruleta Royal"]

# ============================
# FUNCIONES PARA GITHUB
# ============================

def cargar_datos_github():
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        contenido = base64.b64decode(r.json()["content"]).decode()
        sha = r.json()["sha"]
        return json.loads(contenido), sha

    # Archivo no existe → crear uno vacío
    return {}, None


def guardar_datos_github(datos, sha):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    nuevo_contenido = base64.b64encode(json.dumps(datos, indent=4).encode()).decode()

    payload = {
        "message": "Actualización de resultados desde el bot",
        "content": nuevo_contenido
    }

    if sha:
        payload["sha"] = sha  # Necesario si el archivo ya existe

    r = requests.put(url, headers=headers, json=payload)

    return r.status_code in [200, 201]


# ============================
# UTILIDAD: SOLO PRIVADO
# ============================

def solo_privado(update: Update):
    return update.effective_chat.type == "private"


# ============================
# HANDLER /start
# ============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    message = update.message or update.callback_query.message

    await message.reply_text("👋 ¡Bot activo! Estoy listo para registrar resultados.")
    

# ============================
# FLUJO DE REGISTRO /regist
# ============================

async def regist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    message = update.message or update.callback_query.message

    keyboard = [
        [InlineKeyboardButton("Registrar resultados", callback_data="registrar")],
        [InlineKeyboardButton("Cancelar", callback_data="cancelar")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        "¿Deseas registrar los resultados actuales?",
        reply_markup=reply_markup
    )

    return CHOOSING


async def elegir_accion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    query = update.callback_query
    await query.answer()

    if query.data == "registrar":
        keyboard = [[InlineKeyboardButton(l, callback_data=l)] for l in LOTERIAS]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Selecciona la lotería:", reply_markup=reply_markup)
        return LOTERIA

    await query.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


async def elegir_loteria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    query = update.callback_query
    await query.answer()

    context.user_data["loteria"] = query.data
    await query.message.reply_text(f"Ingresar número para {query.data}:")
    return NUMERO


async def recibir_numero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    context.user_data["numero"] = update.message.text
    await update.message.reply_text("Ingresa la hora de salida (HH:MM):")
    return HORA


async def recibir_hora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    loteria = context.user_data["loteria"]
    numero = context.user_data["numero"]
    hora = update.message.text

    datos, sha = cargar_datos_github()

    datos[loteria] = {
        "numero": numero,
        "hora": hora
    }

    exito = guardar_datos_github(datos, sha)

    if exito:
        await update.message.reply_text(
            f"✅ Resultado registrado:\n{loteria} → Número {numero} a las {hora}"
        )
    else:
        await update.message.reply_text("❌ Error al guardar en GitHub.")

    return ConversationHandler.END


# ============================
# MAIN
# ============================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handler de bienvenida
    app.add_handler(CommandHandler("start", start))

    # Handler de registro
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("regist", regist)],
        states={
            CHOOSING: [CallbackQueryHandler(elegir_accion)],
            LOTERIA: [CallbackQueryHandler(elegir_loteria)],
            NUMERO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_numero)],
            HORA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_hora)],
        },
        fallbacks=[CommandHandler("regist", regist)],
    )

    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
