from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import requests
import csv

TOKEN = os.getenv("TOKEN")

# URL del CSV de Google Sheets
https://docs.google.com/spreadsheets/d/1ZdEVbBvs0bWz8ObtfeWYbolD7p-euIZu5Oq5I0WdLyg/export?format=csv

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

    # Descargar CSV
    response = requests.get(URL_SHEETS)
    decoded = response.content.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    # Leer la primera fila
    datos = next(reader)

    loteria = datos["loteria"]
    sorteo = datos["sorteo"]
    favorito = datos["favorito"]
    jugada1 = datos["jugada1"]
    jugada2 = datos["jugada2"]
    jugada3 = datos["jugada3"]

    mensaje = (
        f"LOTERÍA: {loteria}\n"
        f"SORTEO: {sorteo}\n"
        f"FAVORITO: ({favorito})\n"
        f"JUGADA COMPLETA:\n"
        f"({jugada1} -- {jugada2} -- {jugada3})"
    )

    await query.message.reply_text(mensaje)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()
