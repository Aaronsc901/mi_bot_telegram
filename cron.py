import json
import os
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

TOKEN = os.getenv("TOKEN")

# CONFIGURACIÓN DE GITHUB
GITHUB_USER = "Aaronsc901"
REPO = "animalitos_data"
FILE_PATH = "resultados_animalitos.json"
GITHUB_TOKEN = os.getenv("TOKENX")

# Estados
CHOOSING, LOTERIA, LISTA = range(3)

# Loterías
LOTERIAS_NORMALES = ["Guacharo activo", "Lotto activo", "La Granjita"]
LOTERIA_ROYAL = "Ruleta Royal"
LOTERIAS = LOTERIAS_NORMALES + [LOTERIA_ROYAL]

# ============================
# HORARIOS AUTOMÁTICOS
# ============================

def generar_horarios_normales():
    return [f"{h:02d}:00" for h in range(8, 20)]  # 08:00 → 19:00

def generar_horarios_royal():
    return [f"{h:02d}:30" for h in range(8, 21)]  # 08:30 → 20:30

# ============================
# GITHUB
# ============================

def cargar_datos_github():
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        contenido = base64.b64decode(r.json()["content"]).decode()
        sha = r.json()["sha"]
        return json.loads(contenido), sha

    return {}, None

def guardar_datos_github(datos, sha):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    nuevo_contenido = base64.b64encode(json.dumps(datos, indent=4).encode()).decode()

    payload = {
        "message": "Actualización masiva desde el bot",
        "content": nuevo_contenido
    }

    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    return r.status_code in [200, 201]

# ============================
# SOLO PRIVADO
# ============================

def solo_privado(update: Update):
    return update.effective_chat.type == "private"

# ============================
# /start
# ============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    msg = update.message or update.callback_query.message
    await msg.reply_text("👋 Bot activo. Usa /regist para registrar resultados si lo desea.")

# ============================
# /regist
# ============================

async def regist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    msg = update.message or update.callback_query.message

    keyboard = [[InlineKeyboardButton(l, callback_data=l)] for l in LOTERIAS]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg.reply_text("Selecciona la lotería:", reply_markup=reply_markup)
    return LOTERIA

async def elegir_loteria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    query = update.callback_query
    await query.answer()

    context.user_data["loteria"] = query.data

    await query.message.reply_text(
        "Envíame la lista completa de números separados por espacio.\n\n"
        "Ejemplo:\n12 34 56 78 90 11 22 33 44 55 66 77"
    )

    return LISTA

async def recibir_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not solo_privado(update):
        return

    loteria = context.user_data["loteria"]
    lista = [n.strip() for n in update.message.text.split()]

    # Generar horarios
    if loteria == LOTERIA_ROYAL:
        horarios = generar_horarios_royal()
    else:
        horarios = generar_horarios_normales()

    # Rellenar con null si faltan
    resultado = {}
    for i, hora in enumerate(horarios):
        if i < len(lista):
            resultado[hora] = lista[i]
        else:
            resultado[hora] = None

    # Guardar en GitHub
    datos, sha = cargar_datos_github()
    datos[loteria] = resultado

    exito = guardar_datos_github(datos, sha)

    if exito:
        await update.message.reply_text(
            f"🎉 *Registro completado para* *{loteria}*.\n"
            f"📌 *Guardados:* {len(lista)} números\n"
            f"📌 *Rellenados con null:* {len(horarios) - len(lista)}\n\n"
            f"¿Qué deseas hacer ahora?",
            parse_mode="Markdown"
        )

        # MENÚ PREMIUM
        keyboard = [
            [InlineKeyboardButton("➕ Registrar otra lotería", callback_data="otra_loteria")],
            [InlineKeyboardButton(f"🔁 Registrar nuevamente {loteria}", callback_data=f"repetir_{loteria}")],
            [InlineKeyboardButton("📄 Ver horarios", callback_data=f"ver_horarios_{loteria}")],
            [InlineKeyboardButton("❌ Finalizar", callback_data="finalizar")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👇 *Selecciona una opción:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Error al guardar en GitHub.")

    return CHOOSING   # ← CORREGIDO

# ============================
# MENÚ POST REGISTRO
# ============================

async def menu_post_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Registrar otra lotería
    if data == "otra_loteria":
        keyboard = [[InlineKeyboardButton(l, callback_data=l)] for l in LOTERIAS]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "📌 *Selecciona la lotería que deseas registrar:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return LOTERIA

    # Repetir la misma lotería
    if data.startswith("repetir_"):
        loteria = data.replace("repetir_", "")
        context.user_data["loteria"] = loteria

        await query.message.reply_text(
            f"🔁 *Registrar nuevamente {loteria}*\n\n"
            "Envíame la lista completa de números separados por espacio.",
            parse_mode="Markdown"
        )
        return LISTA

    # Ver horarios
    if data.startswith("ver_horarios_"):
        loteria = data.replace("ver_horarios_", "")

        if loteria == LOTERIA_ROYAL:
            horarios = generar_horarios_royal()
        else:
            horarios = generar_horarios_normales()

        texto = "🕒 *Horarios de esta lotería:*\n\n"
        texto += "\n".join([f"• {h}" for h in horarios])

        await query.message.reply_text(texto, parse_mode="Markdown")
        return CHOOSING

    # Finalizar
    if data == "finalizar":
        await query.message.reply_text("👌 Proceso finalizado.")
        return ConversationHandler.END

# ============================
# MAIN
# ============================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("regist", regist)],
        states={
            CHOOSING: [
                CallbackQueryHandler(
                    menu_post_registro,
                    pattern="^(otra_loteria|repetir_.*|ver_horarios_.*|finalizar)$"
                )
            ],
            LOTERIA: [CallbackQueryHandler(elegir_loteria)],
            LISTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_lista)],
        },
        fallbacks=[CommandHandler("regist", regist)],
    )

    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
