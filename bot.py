from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import os
import requests

TOKEN = os.getenv("TOKEN")

# Grupo donde SÍ funciona el bot
GRUPO_PERMITIDO = -1002793980909  # <-- tu ID de grupo

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

    keyboard = [[InlineKeyboardButton("CONSULTAR JUGADA", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Presiona el botón para ver la jugada actual:",
        reply_markup=reply_markup
    )


# -------------------------------
# Callback del botón
# -------------------------------

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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

    return inicio_str, final_str

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

    loteria = datos["loteria"].replace("-", "\\-")
    sorteo = datos["sorteo"].replace("-", "\\-")
    favorito = datos["favorito"].replace("-", "\\-")
    jugada = [str(j).replace("-", "\\-") for j in datos["jugada"]]
    hora = datetime.now(ZoneInfo("America/Caracas")).strftime("%I:%M %p")
    # Calcular margen dinámico
    margen_inicio, margen_final = calcular_margen(datos["hora_tope"], str(datos["intervalo"]))
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
