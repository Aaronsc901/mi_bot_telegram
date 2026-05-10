from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import os

TOKEN = os.getenv("TOKEN")

def start(update, context):
    keyboard = [[InlineKeyboardButton("Consultar número", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Presiona el botón para ver tu número del momento:", reply_markup=reply_markup)

def handle_callback(update, context):
    query = update.callback_query
    query.answer()

    # Aquí pondremos tu lógica real luego
    numero = "34"
    animal = "Venado"

    query.message.reply_text(f"Número del momento: {numero}\nAnimalito: {animal}")

updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CallbackQueryHandler(handle_callback))

updater.start_polling()
