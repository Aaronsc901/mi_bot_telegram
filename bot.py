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
COOLDOWN = 10

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

# ---------------------------------------------------------
# NORMALIZACIÓN ESPECIAL PARA 0 Y 00
# ---------------------------------------------------------

def normalizar_numero(n):
    n = str(n)

    if n == "0":
        return "0"
    if n == "00":
        return "00"

    return n.zfill(2)

# ---------------------------------------------------------
# OBTENER PRÓXIMO SORTEO REAL (solo para bloqueo interno)
# ---------------------------------------------------------

def obtener_proximo_sorteo_real(loteria, horarios):
    ahora = datetime.now(ZoneInfo("America/Caracas"))
    hoy = ahora.date()

    lista = horarios.get(loteria, [])

    proximos = []
    for h in lista:
        hora_dt = datetime.strptime(h, "%H:%M").replace(
            year=hoy.year, month=hoy.month, day=hoy.day,
            tzinfo=ZoneInfo("America/Caracas")
        )
        if hora_dt > ahora:
            proximos.append(hora_dt)

    if proximos:
        return proximos[0]

    # Si no quedan sorteos hoy → primer horario del día siguiente
    primero = datetime.strptime(lista[0], "%H:%M").replace(
        year=hoy.year, month=hoy.month, day=hoy.day,
        tzinfo=ZoneInfo("America/Caracas")
    ) + timedelta(days=1)

    return primero

# ---------------------------------------------------------
# RANGO VISUAL (solo para mostrar al usuario)
# ---------------------------------------------------------

def obtener_rango_visual(loteria, horarios, hora_tope_str):
    ahora = datetime.now(ZoneInfo("America/Caracas"))
    hoy = ahora.date()

    lista = horarios.get(loteria, [])

    hora_tope = datetime.strptime(hora_tope_str, "%H:%M").replace(
        year=hoy.year, month=hoy.month, day=hoy.day,
        tzinfo=ZoneInfo("America/Caracas")
    )

    faltantes = []
    for h in lista:
        hora_dt = datetime.strptime(h, "%H:%M").replace(
            year=hoy.year, month=hoy.month, day=hoy.day,
            tzinfo=ZoneInfo("America/Caracas")
        )
        if ahora < hora_dt <= hora_tope:
            faltantes.append(hora_dt)

    # OPCIÓN C — Si no quedan horarios → mensaje especial
    if not faltantes:
        return None, None

    if len(faltantes) == 1:
        return faltantes[0], None

    return faltantes[0], faltantes[-1]

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

    # ANTI-SPAM
    if user_id in ULTIMA_ACCION:
        if ahora_ts - ULTIMA_ACCION[user_id] < COOLDOWN:
            await query.answer("⏳ Espera unos segundos antes de consultar de nuevo.", show_alert=True)
            return

    ULTIMA_ACCION[user_id] = ahora_ts

    # ANTI DOBLE EJECUCIÓN
    if ahora_ts - ULTIMA_EJECUCION_GLOBAL < COOLDOWN_GLOBAL:
        await query.answer("⚠️ Procesando… intenta nuevamente en un momento.")
        return

    ULTIMA_EJECUCION_GLOBAL = ahora_ts

    await query.answer()

    if not grupo_permitido(query.message.chat.id):
        return

    datos = obtener_datos()

    # ---------------------------------------------------------
    # BLOQUEO INTERNO (≤ 5 minutos para el próximo sorteo real)
    # ---------------------------------------------------------

    ahora = datetime.now(ZoneInfo("America/Caracas"))
    proximo_principal = obtener_proximo_sorteo_real(datos["loteria"], datos["horarios"])

    faltan_principal = (proximo_principal - ahora).total_seconds()

    if 0 < faltan_principal <= 300:
        await query.answer(
            f"⛔ El sorteo de las {proximo_principal.strftime('%I:%M %p')} ya está cerrado.",
            show_alert=True
        )
        return

    # ---------------------------------------------------------
    # DATOS PRINCIPALES
    # ---------------------------------------------------------

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

    # ✅ CORRECCIÓN: usar hora_tope como referencia
    hora_tope_dt = datetime.strptime(datos["hora_tope"], "%H:%M").replace(
        year=ahora.year, month=ahora.month, day=ahora.day,
        tzinfo=ZoneInfo("America/Caracas")
        print("AHORA:", ahora.strftime("%H:%M"))
        print("HORA_TOPE:", hora_tope_dt.strftime("%H:%M"))
        print("FALTAN SEGUNDOS:", faltan_para_tope)

    )
    faltan_para_tope = (hora_tope_dt - ahora).total_seconds()

    activar_por_tiempo = faltan_para_tope <= 3600
    usar_opcional = repetidos or activar_por_tiempo

    # ---------------------------------------------------------
    # RANGO VISUAL PRINCIPAL
    # ---------------------------------------------------------

    inicio_visual, fin_visual = obtener_rango_visual(
        datos["loteria"], datos["horarios"], datos["hora_tope"]
    )

    if inicio_visual is None:
        sorteo_texto = "⚠️ No quedan sorteos disponibles hoy."
    else:
        if fin_visual:
            sorteo_texto = f"{inicio_visual.strftime('%I:%M %p')} - {fin_visual.strftime('%I:%M %p')}"
        else:
            sorteo_texto = inicio_visual.strftime("%I:%M %p")

    # ---------------------------------------------------------
    # JUGADA SECUNDARIA (OPCIONAL)
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

            # BLOQUEO INTERNO OPCIONAL
            proximo_opcional = obtener_proximo_sorteo_real(loteria_opcional_tecnica, datos["horarios"])
            faltan_opcional = (proximo_opcional - ahora).total_seconds()

            if 0 < faltan_opcional <= 300:
                await query.answer(
                    f"⚠️ La jugada opcional existe, pero el sorteo de las "
                    f"{proximo_opcional.strftime('%I:%M %p')} ya está cerrado.",
                    show_alert=True
                )
                return

            # RANGO VISUAL OPCIONAL
            inicio_visual, fin_visual = obtener_rango_visual(
                loteria_opcional_tecnica, datos["horarios"], datos["hora_tope"]
            )

            if inicio_visual is None:
                sorteo_texto = "⚠️ No quedan sorteos disponibles hoy."
            else:
                if fin_visual:
                    sorteo_texto = f"{inicio_visual.strftime('%I:%M %p')} - {fin_visual.strftime('%I:%M %p')}"
                else:
                    sorteo_texto = inicio_visual.strftime("%I:%M %p")

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
    datos["margen_opcional_activado"] = None
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
