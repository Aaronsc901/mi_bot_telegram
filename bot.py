from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import requests

TOKEN = os.getenv("TOKEN")

# URL RAW del archivo JSON en GitHub
URL_DATOS = "https://raw.githubusercontent.com/Aaronsc901/mi_bot_telegram/master/datos.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Consultar número", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Presiona el botón para ver tu número del momento:",
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Leer datos desde GitHub
    datos = requests.get(URL_DATOS).json()

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

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()
