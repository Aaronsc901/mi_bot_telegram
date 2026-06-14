import os
import json
import base64
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------------------------------------------------
# CARGAR DICCIONARIO DE ANIMALITOS
# ---------------------------------------------------------

def cargar_diccionario():
    url = "https://raw.githubusercontent.com/Aaronsc901/mi_bot_telegram/master/diccionario_animalitos.json"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        return json.loads(r.text)
    except Exception as e:
        print("ERROR cargando diccionario:", e)
        return {}

DICCIONARIO = cargar_diccionario()

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------

TOKEN = os.getenv("TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_API_URL = "https://api.github.com/repos/Aaronsc901/mi_bot_telegram/contents/datos.json?ref=master"

GRUPO_REAL_ID = -1002793980909
GRUPO_TEST_ID = -1004319978717

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
    h_inicio = datetime.strptime(inicio_str, "%H:%M").time()
    h_fin = datetime.strptime(fin_str, "%H:%M").time()
    return h_inicio <= hora_actual <= h_fin

# ---------------------------------------------------------
# AJUSTE DINÁMICO DEL RANGO (LÓGICA DEL BOT ANTERIOR)
# ---------------------------------------------------------

def ajustar_rango_dinamico(rango_inicio_str, rango_fin_str, ahora):
    # Convertir strings a objetos datetime.time
    r_inicio = datetime.strptime(rango_inicio_str, "%H:%M").time()
    r_fin = datetime.strptime(rango_fin_str, "%H:%M").time()

    # Función interna para formatear a 12h
    def formato_12h(t):
        return datetime.strptime(t.strftime("%H:%M"), "%H:%M").strftime("%I:%M %p")

    # Antes del rango → mostrar completo
    if ahora.time() < r_inicio:
        return f"{formato_12h(r_inicio)} - {formato_12h(r_fin)}"

    # Después del rango → solo hora final
    if ahora.time() >= r_fin:
        return f"{formato_12h(r_fin)}"

    # Dentro del rango → ajustar a la próxima hora entera
    siguiente_hora = (ahora.replace(minute=0, second=0, microsecond=0)
                      .replace(hour=ahora.hour + 1))

    inicio_dinamico = max(siguiente_hora.time(), r_inicio)

    # Si el inicio dinámico coincide con el final → solo hora final
    if inicio_dinamico >= r_fin:
        return f"{formato_12h(r_fin)}"

    # Mostrar rango ajustado
    return f"{formato_12h(inicio_dinamico)} - {formato_12h(r_fin)}"


# ---------------------------------------------------------
# BUSCAR JUGADA EN CURSO AUNQUE NO HAYA VENTANA ACTIVA
# ---------------------------------------------------------

def buscar_jugada_en_curso(datos, ahora):
    for loteria in datos["loterias"]:
        for ventana in loteria["ventanas"]:
            r_inicio = datetime.strptime(ventana["rango_inicio"], "%H:%M").time()
            r_fin = datetime.strptime(ventana["rango_fin"], "%H:%M").time()

            if r_inicio <= ahora.time() <= r_fin:
                return {
                    "visible": loteria["visible"],
                    "rango_inicio": ventana["rango_inicio"],
                    "rango_fin": ventana["rango_fin"],
                    "jugada": ventana["jugada"]
                }
    return None

# ---------------------------------------------------------
# SELECCIÓN DE LOTERÍA SEGÚN VENTANAS
# ---------------------------------------------------------

def obtener_loteria_activa(datos, hora_actual=None):
    if hora_actual is None:
        hora_actual = datetime.now(ZoneInfo("America/Caracas")).time()

    for loteria in datos["loterias"]:
        for ventana in loteria["ventanas"]:
            if hora_en_rango(hora_actual, ventana["activar_inicio"], ventana["activar_fin"]):
                return {
                    "visible": loteria["visible"],
                    "rango_inicio": ventana["rango_inicio"],
                    "rango_fin": ventana["rango_fin"],
                    "jugada": ventana["jugada"]
                }

    return None

# ---------------------------------------------------------
# OBTENER FAVORITO + NOMBRE
# ---------------------------------------------------------

def obtener_favorito(jugada):
    if not jugada:
        return None, None

    favorito_num = jugada[0]
    favorito_nombre = None

    if "Lotto Activo" in DICCIONARIO:
        if favorito_num in DICCIONARIO["Lotto Activo"]:
            return favorito_num, DICCIONARIO["Lotto Activo"][favorito_num]

    for base in DICCIONARIO.values():
        if favorito_num in base:
            favorito_nombre = base[favorito_num]
            break

    return favorito_num, favorito_nombre

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
    ahora = datetime.now(ZoneInfo("America/Caracas"))

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

    # NUEVA LÓGICA: si no hay ventana activa, buscar jugada en curso
    if not loteria:
        jugada_curso = buscar_jugada_en_curso(datos, ahora)

        if not jugada_curso:
            await query.answer("📵 Actualmente no hay actualización disponible.", show_alert=True)
            return

        loteria = jugada_curso

    # Preparar jugada
    jugada = [md_escape(j) for j in loteria["jugada"]]
    jugada_texto = " \\- ".join([f"*{j}*" for j in jugada]) if jugada else "*Sin jugada cargada*"

    favorito_num, favorito_nombre = obtener_favorito(loteria["jugada"])

    if favorito_num:
        if favorito_nombre:
            favorito_texto = f"*{md_escape(favorito_num)} \\({md_escape(favorito_nombre)}\\)*"
        else:
            favorito_texto = f"*{md_escape(favorito_num)}*"
    else:
        favorito_texto = "*N/A*"

    # Rango dinámico
    rango_dinamico = ajustar_rango_dinamico(
        loteria["rango_inicio"],
        loteria["rango_fin"],
        ahora
    )

    mensaje = (
        "🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{ahora.strftime('%I:%M %p')}`\n\n"
        f"🎯 *Lotería:* *{md_escape(loteria['visible'])}*\n"
        f"🕒 *Sorteo:* `{rango_dinamico}`\n"
        f"🐾 *Favorito:* {favorito_texto}\n\n"
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
# COMANDO /simular HH:MM
# ---------------------------------------------------------

async def simular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not grupo_permitido(update.effective_chat.id):
        return

    if len(context.args) != 1:
        await update.message.reply_text("Uso correcto:\n/simular HH:MM")
        return

    try:
        hora_simulada = datetime.strptime(context.args[0], "%H:%M").time()
    except:
        await update.message.reply_text("Formato inválido. Usa HH:MM (ej: 14:25)")
        return

    datos = cargar_json_remoto()
    loteria = obtener_loteria_activa(datos, hora_simulada)

    ahora = datetime.now(ZoneInfo("America/Caracas")).replace(
        hour=hora_simulada.hour,
        minute=hora_simulada.minute,
        second=0,
        microsecond=0
    )

    if not loteria:
        jugada_curso = buscar_jugada_en_curso(datos, ahora)
        if not jugada_curso:
            await update.message.reply_text("📵 Actualmente no hay actualización disponible.")
            return
        loteria = jugada_curso

    jugada = [md_escape(j) for j in loteria["jugada"]]
    jugada_texto = " \\- ".join([f"*{j}*" for j in jugada]) if jugada else "*Sin jugada cargada*"

    favorito_num, favorito_nombre = obtener_favorito(loteria["jugada"])

    if favorito_num:
        if favorito_nombre:
            favorito_texto = f"*{md_escape(favorito_num)} \\({md_escape(favorito_nombre)}\\)*"
        else:
            favorito_texto = f"*{md_escape(favorito_num)}*"
    else:
        favorito_texto = "*N/A*"

    rango_dinamico = ajustar_rango_dinamico(
        loteria["rango_inicio"],
        loteria["rango_fin"],
        ahora
    )

    mensaje = (
        "🧪 *SIMULACIÓN DE JUGADA* 🧪\n"
        f"🕒 *Hora simulada:* `{context.args[0]}`\n\n"
        f"🎯 *Lotería:* *{md_escape(loteria['visible'])}*\n"
        f"🕒 *Sorteo:* `{rango_dinamico}`\n"
        f"🐾 *Favorito:* {favorito_texto}\n\n"
        "🔢 *Jugada simulada:*\n"
        f"{jugada_texto}"
    )

    await update.message.reply_text(mensaje, parse_mode="MarkdownV2")

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
    app.add_handler(CommandHandler("simular", simular))
    app.add_handler(CallbackQueryHandler(handle_callback))

    cargar_modo_test()
    app.run_polling()

if __name__ == "__main__":
    main()
