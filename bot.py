import os
import json
import base64
import requests
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------

TOKEN = os.getenv("TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_API_URL = "https://api.github.com/repos/Aaronsc901/mi_bot_telegram/contents/datos.json?ref=master"

GRUPO_REAL_ID = -1004319978717
GRUPO_TEST_ID = -5197810505

MODO_TEST = True

# ---------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------

def md_escape(text: str) -> str:
    especiales = r"_*[]()~`>#+-=|{}"
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
        "message": "Actualización automática de jugadas",
        "content": nuevo_contenido,
        "sha": sha
    }

    requests.put(GITHUB_API_URL, headers=headers, json=payload)

# ---------------------------------------------------------
# PUBLICAR MENSAJE AUTOMÁTICO
# ---------------------------------------------------------

async def publicar_jugada(bot, loteria, hora, jugadas):
    ahora = datetime.now(ZoneInfo("America/Caracas"))

    jugada_norm = [normalizar_numero(j) for j in jugadas]
    jugada_texto = " \\- ".join([f"*{md_escape(j)}*" for j in jugada_norm])

    mensaje = (
        "🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{ahora.strftime('%I:%M %p')}`\n\n"
        f"🎯 *Lotería:* *{md_escape(loteria)}*\n"
        f"🕒 *Sorteo:* `{hora}`\n\n"
        "🔢 *Jugada del momento:*\n"
        f"{jugada_texto}"
    )

    chat_destino = GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID

    msg = await bot.send_message(
        chat_destino,
        mensaje,
        parse_mode="MarkdownV2"
    )

    return msg.message_id

# ---------------------------------------------------------
# LIMPIAR MENSAJES (MÁXIMO 3 ACTIVOS)
# ---------------------------------------------------------

async def limpiar_mensajes(bot, datos):
    chat_destino = GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID
    mensajes = datos.get("mensajes_activos", [])

    if len(mensajes) <= 3:
        return

    borrar = mensajes[:-3]

    for msg_id in borrar:
        try:
            await bot.delete_message(chat_id=chat_destino, message_id=msg_id)
        except:
            pass

    datos["mensajes_activos"] = mensajes[-3:]
    guardar_datos(datos)

# ---------------------------------------------------------
# PUBLICADOR AUTOMÁTICO (POR RANGO)
# ---------------------------------------------------------

async def publicador_automatico(bot):
    datos = obtener_datos()
    ahora = datetime.now(ZoneInfo("America/Caracas"))

    hora_actual = ahora.strftime("%H:%M")
    hora_actual_dt = datetime.strptime(hora_actual, "%H:%M")

    cambios = False

    for lot in datos.get("auto_loterias", []):
        nombre = lot["nombre"]
        horas = lot["horas"]
        jugadas = lot["jugadas"]
        publicadas = lot["publicadas"]

        for h in horas:
            if h in publicadas:
                continue

            hora_dt = datetime.strptime(h, "%H:%M")

            # PUBLICA SI LA HORA YA PASÓ O ES IGUAL
            if hora_dt <= hora_actual_dt:
                msg_id = await publicar_jugada(bot, nombre, h, jugadas)
                datos["mensajes_activos"].append(msg_id)
                publicadas.append(h)
                cambios = True

    if cambios:
        guardar_datos(datos)
        await limpiar_mensajes(bot, datos)

# ---------------------------------------------------------
# CICLO AUTOMÁTICO SIN JOB_QUEUE
# ---------------------------------------------------------

async def ciclo_publicador(app):
    await asyncio.sleep(5)
    while True:
        try:
            await publicador_automatico(app.bot)
        except Exception as e:
            print("Error en publicador_automatico:", e)
        await asyncio.sleep(60)

# ---------------------------------------------------------
# COMANDO /cargar_auto
# ---------------------------------------------------------

async def cargar_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = obtener_datos()

    for lot in datos.get("auto_loterias", []):
        lot["publicadas"] = []

    datos["mensajes_activos"] = []

    guardar_datos(datos)

    await update.message.reply_text("Jugadas automáticas cargadas para el día.")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("cargar_auto", cargar_auto))

    loop = asyncio.get_event_loop()
    loop.create_task(ciclo_publicador(app))

    app.run_polling()

if __name__ == "__main__":
    main()
