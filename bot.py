from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import requests

TOKEN = os.getenv("TOKEN")

# ⛔ SOLO ESTE GRUPO PUEDE USAR EL BOT
GRUPO_PERMITIDO = -1002793980909  # <-- coloca aquí tu ID real

# URL RAW del archivo JSON en GitHub
URL_DATOS = "https://raw.githubusercontent.com/Aaronsc901/mi_bot_telegram/master/datos.json"

# Comando /start (solo funciona en el grupo permitido)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_PERMITIDO:
        return  # Ignorar privados y otros grupos

    keyboard = [[InlineKeyboardButton("CONSULTAR JUGADA", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Presiona el botón para ver la jugada actual:",
        reply_markup=reply_markup
    )

# Botón (callback) — también filtrado por grupo
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.message.chat.id != GRUPO_PERMITIDO:
        await query.answer("Este bot solo funciona en el grupo autorizado.")
        return

    await query.answer()

    # Leer datos desde GitHub
    response = requests.get(URL_DATOS)
    datos = response.json()

    loteria = datos["loteria"]
    sorteo = datos["sorteo"]
    favorito = datos["favorito"]
    jugada = datos["jugada"]

    mensaje = (
        f"LOTERÍA: {loteria}\n"
        f"SORTEO: {sorteo}\n"
        f"FAVORITO: ({favorito})\n"
        f"JUGADA COMPLETA:\n"
        f"({jugada[0]} -- {jugada[1]} -- {jugada[2]})"
    )

    await query.message.reply_text(mensaje)

# Comando /id (puedes borrarlo después de usarlo)
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    #app.add_handler(CommandHandler("id", get_id))  # opcional
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()

if __name__ == "__main__":
    main()
