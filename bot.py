import os
import json
import base64
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from validacion import validar_jugada

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

MODO_TEST = True
GRUPO_REAL_ID = -1002793980909
GRUPO_TEST_ID = -5197810505

def grupo_permitido(chat_id):
    return chat_id == (GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID)

MENSAJE_FIJO_ID = None

# ---------------------------------------------------------
# ANTI‑SPAM Y ANTI‑DOBLE EJECUCIÓN
# ---------------------------------------------------------

ULTIMA_ACCION = {}
COOLDOWN = 60  # 60 segundos por usuario

ULTIMA_EJECUCION_GLOBAL = 0
COOLDOWN_GLOBAL = 3

# ---------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------

def md_escape(text: str) -> str:
    especiales = r"_*[]()~`>#+-=|{}.!"""
    for c in especiales:
        text = text.replace(c, f"\\{c}")
    return text

def normalizar_numero(n):
    n = str(n)
    if n == "0":
        return "0"
    if n == "00":
        return "00"
    return n.zfill(2)

# ---------------------------------------------------------
# LECTURA DEL JSON REMOTO
# ---------------------------------------------------------

def obtener_datos():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(GITHUB_API_URL, headers=headers).json()

    contenido = base64.b64decode(r["content"]).decode()
    datos = json.loads(contenido)

    datos["_sha"] = r["sha"]
    return datos

# ---------------------------------------------------------
# ESCRITURA DEL JSON REMOTO
# ---------------------------------------------------------

def guardar_datos(datos):
    sha = datos.pop("_sha")

    nuevo_contenido = base64.b64encode(
        json.dumps(datos, indent=2).encode()
    ).decode()

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    payload = {
        "message": "Actualización automática del margen opcional",
        "content": nuevo_contenido,
        "sha": sha
    }

    requests.put(GITHUB_API_URL, headers=headers, json=payload)

# ---------------------------------------------------------
# CÁLCULO DE MARGEN PRINCIPAL
# ---------------------------------------------------------

def calcular_margen(hora_tope_str, intervalo):
    ahora = datetime.now(ZoneInfo("America/Caracas"))

    if intervalo == "60":
        margen_inicio = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    elif intervalo == "30":
        minuto = ahora.minute
        if minuto <= 30:
            margen_inicio = ahora.replace(minute=30, second=0, microsecond=0)
        else:
            siguiente_hora = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            margen_inicio = siguiente_hora.replace(minute=30)

    hora_tope = datetime.strptime(hora_tope_str, "%H:%M").time()
    margen_final = datetime.combine(ahora.date(), hora_tope)

    return (
        margen_inicio.strftime("%I:%M %p"),
        margen_final.strftime("%I:%M %p")
    )

# ---------------------------------------------------------
# CORRECCIÓN AUTOMÁTICA DE MÁRGENES VIEJOS
# ---------------------------------------------------------

def margen_es_viejo(m_inicio, m_final, ahora):
    try:
        mi = datetime.strptime(m_inicio, "%I:%M %p").replace(
            year=ahora.year, month=ahora.month, day=ahora.day, tzinfo=ZoneInfo("America/Caracas")
        )
        mf = datetime.strptime(m_final, "%I:%M %p").replace(
            year=ahora.year, month=ahora.month, day=ahora.day, tzinfo=ZoneInfo("America/Caracas")
        )

        # Si el margen final ya pasó hace más de 5 minutos → margen viejo
        if (ahora - mf).total_seconds() > 300:
            return True

        # Si el margen final está antes del inicio → margen corrupto
        if mf < mi:
            return True

        return False

    except:
        return True  # Si falla el parseo, lo tratamos como viejo

# ---------------------------------------------------------
# COMANDO /start
# ---------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not grupo_permitido(update.effective_chat.id):
        return

    msg = update.message or update.callback_query.message

    keyboard = [[InlineKeyboardButton("CONSULTAR JUGADA", callback_data="consulta")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg.reply_text(
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

    # ANTI-SPAM POR USUARIO
    if user_id in ULTIMA_ACCION:
        diferencia = ahora_ts - ULTIMA_ACCION[user_id]
        if diferencia < COOLDOWN:
            faltan = int(COOLDOWN - diferencia)
            await query.answer(f"⏳ Debes esperar {faltan} segundos para volver a consultar.", show_alert=True)
            return

    ULTIMA_ACCION[user_id] = ahora_ts

    # ANTI DOBLE EJECUCIÓN GLOBAL
    if ahora_ts - ULTIMA_EJECUCION_GLOBAL < COOLDOWN_GLOBAL:
        await query.answer("⚠️ Procesando… intenta nuevamente en un momento.", show_alert=False)
        return

    ULTIMA_EJECUCION_GLOBAL = ahora_ts

    await query.answer()

    if not grupo_permitido(query.message.chat.id):
        return

    datos = obtener_datos()

    # DATOS PRINCIPALES
    loteria_tecnica = datos["loteria"]
    loteria_visible = datos.get("loteria_visible", datos["loteria"])

    jugada_numeros = [normalizar_numero(j) for j in datos["jugada"]]
    jugada = [md_escape(normalizar_numero(j)) for j in datos["jugada"]]

    favorito_num = jugada_numeros[0]

    lt = loteria_tecnica.lower()

    if "lotto" in lt and "granjita" in lt:
        diccionario_base = "Lotto Activo"
    elif "lotto" in lt:
        diccionario_base = "Lotto Activo"
    elif "granjita" in lt:
        diccionario_base = "La Granjita"
    else:
        diccionario_base = loteria_tecnica

    favorito_nombre = DICCIONARIO.get(diccionario_base, {}).get(favorito_num, "DESCONOCIDO")
    favorito = md_escape(f"{favorito_num} ({favorito_nombre})")

    repetidos = validar_jugada(loteria_tecnica, jugada_numeros)

    margen_inicio, margen_final = calcular_margen(datos["hora_tope"], str(datos["intervalo"]))

    # ---------------------------------------------------------
    # CORRECCIÓN AUTOMÁTICA DE MÁRGENES VIEJOS (PRINCIPAL)
    # ---------------------------------------------------------

    if margen_es_viejo(margen_inicio, margen_final, ahora):
        margen_inicio, margen_final = calcular_margen(datos["hora_tope"], str(datos["intervalo"]))

    # ---------------------------------------------------------
    # BLOQUEO POR TIEMPO (AMBOS MÁRGENES)
    # ---------------------------------------------------------

    def bloquear_por_tiempo(m_inicio, m_final):
        mi = datetime.strptime(m_inicio, "%I:%M %p").replace(
            year=ahora.year, month=ahora.month, day=ahora.day, tzinfo=ZoneInfo("America/Caracas")
        )
        mf = datetime.strptime(m_final, "%I:%M %p").replace(
            year=ahora.year, month=ahora.month, day=ahora.day, tzinfo=ZoneInfo("America/Caracas")
        )

        # Faltan menos de 8 minutos
        if 0 <= (mi - ahora).total_seconds() <= 480:
            return True

        # Pasaron más de 5 minutos
        if (ahora - mf).total_seconds() > 300:
            return True

        return False

    # Bloqueo margen principal
    if bloquear_por_tiempo(margen_inicio, margen_final):
        await query.answer("⛔ Consulta no disponible en este momento.", show_alert=True)
        return

    activar_por_tiempo = (datetime.strptime(margen_final, "%I:%M %p") - ahora).total_seconds() <= 3600
    usar_opcional = repetidos or activar_por_tiempo

    # ---------------------------------------------------------
    # JUGADA SECUNDARIA (CON MARGEN CONGELADO + CORRECCIÓN)
    # ---------------------------------------------------------

    if usar_opcional:
        jugada_opcional = datos.get("jugada_opcional", [])
        loteria_opcional_tecnica = datos.get("loteria_opcional", None)
        loteria_opcional_visible = datos.get("loteria_opcional_visible", loteria_opcional_tecnica)

        if jugada_opcional and loteria_opcional_tecnica:

            jugada_opcional_norm = [normalizar_numero(j) for j in jugada_opcional]
            repetidos_opcional = validar_jugada(loteria_opcional_tecnica, jugada_opcional_norm)

            if repetidos_opcional:
                await query.answer(
                    "❌ No hay nueva jugada disponible por el momento.",
                    show_alert=True
                )
                return

            # SI YA EXISTE MARGEN CONGELADO → VALIDARLO
            if datos.get("margen_opcional_inicio") and datos.get("margen_opcional_final"):

                if margen_es_viejo(datos["margen_opcional_inicio"], datos["margen_opcional_final"], ahora):
                    datos["margen_opcional_inicio"] = None
                    datos["margen_opcional_final"] = None
                    guardar_datos(datos)
                else:
                    margen_inicio = datos["margen_opcional_inicio"]
                    margen_final = datos["margen_opcional_final"]

            # SI NO EXISTE → CALCULAR Y CONGELAR
            if datos.get("margen_opcional_inicio") is None:

                intervalo_secundario = 30 if "ruleta" in loteria_opcional_tecnica.lower() else 60

                if intervalo_secundario == 60:
                    margen_inicio_dt = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                else:
                    minuto = ahora.minute
                    if minuto < 30:
                        margen_inicio_dt = ahora.replace(minute=30, second=0, microsecond=0)
                    else:
                        siguiente_hora = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                        margen_inicio_dt = siguiente_hora.replace(minute=30)

                margen_final_dt = margen_inicio_dt + timedelta(hours=4)

                if intervalo_secundario == 60:
                    limite = margen_inicio_dt.replace(hour=19, minute=0, second=0, microsecond=0)
                else:
                    limite = margen_inicio_dt.replace(hour=20, minute=30, second=0, microsecond=0)

                if margen_final_dt > limite:
                    margen_final_dt = limite

                margen_inicio = margen_inicio_dt.strftime("%I:%M %p")
                margen_final = margen_final_dt.strftime("%I:%M %p")

                datos["margen_opcional_inicio"] = margen_inicio
                datos["margen_opcional_final"] = margen_final
                guardar_datos(datos)

            # BLOQUEO TAMBIÉN PARA EL MARGEN SECUNDARIO
            if bloquear_por_tiempo(margen_inicio, margen_final):
                await query.answer("⛔ Consulta no disponible en este momento.", show_alert=True)
                return

            # CAMBIAR JUGADA
            jugada = [md_escape(j) for j in jugada_opcional_norm]
            favorito_num = jugada_opcional_norm[0]

            lt2 = loteria_opcional_tecnica.lower()

            if "lotto" in lt2 and "granjita" in lt2:
                diccionario_base2 = "Lotto Activo"
            elif "lotto" in lt2:
                diccionario_base2 = "Lotto Activo"
            elif "granjita" in lt2:
                diccionario_base2 = "La Granjita"
            else:
                diccionario_base2 = loteria_opcional_tecnica

            favorito_nombre = DICCIONARIO.get(diccionario_base2, {}).get(favorito_num, "DESCONOCIDO")
            favorito = md_escape(f"{favorito_num} ({favorito_nombre})")

            loteria_visible = loteria_opcional_visible

    # ---------------------------------------------------------
    # MENSAJE FINAL
    # ---------------------------------------------------------

    jugada_texto = " \\- ".join([f"*{j}*" for j in jugada])

    if margen_final:
        sorteo_texto = f"{margen_inicio} - {margen_final}"
    else:
        sorteo_texto = margen_inicio

    mensaje = (
        "🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{ahora.strftime('%I:%M %p')}`\n\n"
        f"🎯 *Lotería:* *{md_escape(loteria_visible)}*\n"
        f"🕒 *Sorteo:* `{sorteo_texto}`\n"
        f"🐾 *Favorito:* *{favorito}*\n\n"
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

    datos = obtener_datos()
    datos["margen_opcional_inicio"] = None
    datos["margen_opcional_final"] = None
    guardar_datos(datos)

    await update.message.reply_text("Reiniciado. El próximo mensaje será nuevo.")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()

if __name__ == "__main__":
    main()
