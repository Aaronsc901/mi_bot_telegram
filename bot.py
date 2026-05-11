from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import requests

TOKEN = os.getenv("TOKEN")

# Grupo donde SÍ funciona el bot
GRUPO_PERMITIDO = -1002793980909 # <-- tu ID de grupo

# URL RAW del JSON
URL_DATOS = "https://raw.githubusercontent.com/Aaronsc901/mi_bot_telegram/master/datos.json"

# Variable global para mantener un solo mensaje
MENSAJE_FIJO_ID = None


# -------------------------------
# Comando /start
# -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_PERMITIDO:
        return

    keyboard = [[InlineKeyboardButton("CONSULTA LA JUGADA", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Presiona el botón para ver la jugada actual:",
        reply_markup=reply_markup
    )


# -------------------------------
# Callback del botón
# -------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MENSAJE_FIJO_ID
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

    # Formato premium con Markdown V2
    mensaje = (
        f"🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{context.application.timezone.localize(datetime.now()).strftime('%I:%M %p')}`\n\n"
        f"🎯 *Lotería:* *{loteria}*\n"
        f"🕒 *Sorteo:* *{sorteo}*\n"
        f"🐾 *Favorito:* *{favorito}*\n\n"
        f"🔢 *Jugada del momento:*\n"
        f"*{jugada[0]}* \- *{jugada[1]}* \- *{jugada[2]}*"
    )

    # Intentar editar el mensaje fijo si existe
    if MENSAJE_FIJO_ID:
        try:
            await context.bot.edit_message_text(
                chat_id=GRUPO_PERMITIDO,
                message_id=MENSAJE_FIJO_ID,
                text=mensaje,
                parse_mode="MarkdownV2"
            )
            return
        except:
            pass  # Si falla, enviamos uno nuevo

    # Crear mensaje nuevo y guardar ID
    msg = await query.message.reply_text(mensaje, parse_mode="MarkdownV2")
    MENSAJE_FIJO_ID = msg.message_id


# -------------------------------
# Comando /id (opcional)
# -------------------------------
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


# -------------------------------
# MAIN
# -------------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    #app.add_handler(CommandHandler("id", get_id))  # opcional
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()


if __name__ == "__main__":
    main()
