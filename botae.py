import asyncio
import os
import json
import base64
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

# =========================================================
# CONFIG
# =========================================================

load_dotenv(dotenv_path="/root/mi_bot_telegram/.env", override=True)

TOKEN = os.getenv("TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

GRUPO_REAL_ID = -1002793980909
GRUPO_TEST_ID = -1003708520026

MODO_TEST = None
MENSAJE_FIJO_ID = None

ULTIMA_ACCION = {}
COOLDOWN = 30

ULTIMA_EJECUCION_GLOBAL = 0
COOLDOWN_GLOBAL = 3

GITHUB_API_URL = "https://api.github.com/repos/Aaronsc901/mi_bot_telegram/contents/datos.json?ref=master"

# =========================================================
# DICCIONARIO ANIMALITOS
# =========================================================

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

# =========================================================
# UTILIDADES
# =========================================================

def md_escape(text: str) -> str:
    especiales = r"_*[]()~`>#+-=|{}"
    for c in especiales:
        text = text.replace(c, f"\\{c}")
    return text

def cargar_json_remoto():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(GITHUB_API_URL, headers=headers, timeout=5)
        r.raise_for_status()
        contenido = base64.b64decode(r.json()["content"]).decode()
        datos = json.loads(contenido)
        datos["_sha"] = r.json()["sha"]
        return datos
    except Exception as e:
        print("ERROR cargando JSON remoto:", e)
        return {"loterias": []}

def cargar_modo_test():
    global MODO_TEST
    try:
        datos = cargar_json_remoto()
        MODO_TEST = datos.get("modo_test", False)
    except:
        MODO_TEST = False

def grupo_permitido(chat_id):
    cargar_modo_test()
    return chat_id == (GRUPO_TEST_ID if MODO_TEST else GRUPO_REAL_ID)

def hora_en_rango(hora_actual, inicio_str, fin_str):
    h_inicio = datetime.strptime(inicio_str, "%H:%M").time()
    h_fin = datetime.strptime(fin_str, "%H:%M").time()
    return h_inicio <= hora_actual <= h_fin

def ajustar_rango_dinamico(rango_inicio_str, rango_fin_str, ahora):
    r_inicio = datetime.strptime(rango_inicio_str, "%H:%M").time()
    r_fin = datetime.strptime(rango_fin_str, "%H:%M").time()

    def formato_12h(t):
        return datetime.strptime(t.strftime("%H:%M"), "%H:%M").strftime("%I:%M %p")

    if ahora.time() < r_inicio:
        return f"{formato_12h(r_inicio)} - {formato_12h(r_fin)}"

    if ahora.time() >= r_fin:
        return f"{formato_12h(r_fin)}"

    siguiente_hora = (ahora.replace(minute=0, second=0, microsecond=0)
                      .replace(hour=ahora.hour + 1))

    inicio_dinamico = max(siguiente_hora.time(), r_inicio)

    if inicio_dinamico >= r_fin:
        return f"{formato_12h(r_fin)}"

    return f"{formato_12h(inicio_dinamico)} - {formato_12h(r_fin)}"

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

# =========================================================
# /start
# =========================================================

@router.message(Command("start"))
async def start(message: types.Message):
    if not grupo_permitido(message.chat.id):
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="CONSULTAR JUGADA", callback_data="consulta")]
        ]
    )

    await message.answer(
        "Presiona el botón para ver la jugada actual:",
        reply_markup=keyboard
    )

# =========================================================
# CALLBACK PRINCIPAL
# =========================================================

@router.callback_query(lambda c: c.data == "consulta")
async def handle_callback(callback: types.CallbackQuery):
    global MENSAJE_FIJO_ID, ULTIMA_EJECUCION_GLOBAL

    user_id = callback.from_user.id
    ahora_ts = datetime.now().timestamp()
    ahora = datetime.now(ZoneInfo("America/Caracas"))

    if user_id in ULTIMA_ACCION:
        if ahora_ts - ULTIMA_ACCION[user_id] < COOLDOWN:
            await callback.answer("⏳ Espera unos segundos antes de consultar de nuevo.", show_alert=True)
            return

    ULTIMA_ACCION[user_id] = ahora_ts

    if ahora_ts - ULTIMA_EJECUCION_GLOBAL < COOLDOWN_GLOBAL:
        await callback.answer("⚠️ Procesando… intenta nuevamente en un momento.")
        return

    ULTIMA_EJECUCION_GLOBAL = ahora_ts

    await callback.answer()

    if not grupo_permitido(callback.message.chat.id):
        return

    datos = cargar_json_remoto()
    loteria = obtener_loteria_activa(datos)

    if not loteria:
        jugada_curso = buscar_jugada_en_curso(datos, ahora)
        if not jugada_curso:
            await callback.answer("📵 Actualmente no hay actualización disponible.", show_alert=True)
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
        "🔥 *ACTUALIZACIÓN DE JUGADA* 🔥\n"
        f"📅 *Última actualización:* `{ahora.strftime('%I:%M %p')}`\n\n"
        f"🎯 *Lotería:* *{md_escape(loteria['visible'])}*\n"
        f"🕒 *Sorteo:* `{rango_dinamico}`\n"
        f"🐾 *Favorito:* {favorito_texto}\n\n"
        "🔢 *Jugada del momento:*\n"
        f"{jugada_texto}"
    )

    chat_destino = callback.message.chat.id

    if MENSAJE_FIJO_ID:
        try:
            await bot.delete_message(chat_destino, MENSAJE_FIJO_ID)
        except:
            pass

    msg = await bot.send_message(
        chat_destino,
        mensaje,
        parse_mode="MarkdownV2"
    )

    MENSAJE_FIJO_ID = msg.message_id

# =========================================================
# /multi
# =========================================================

@router.message(Command("multi"))
async def multi(message: types.Message):
    if not grupo_permitido(message.chat.id):
        return

    ahora = datetime.now(ZoneInfo("America/Caracas"))
    datos = cargar_json_remoto()

    jugadas_activas = []

    for loteria in datos["loterias"]:
        for ventana in loteria["ventanas"]:
            a_inicio = datetime.strptime(ventana["activar_inicio"], "%H:%M").time()
            r_fin = datetime.strptime(ventana["rango_fin"], "%H:%M").time()

            if a_inicio <= ahora.time() <= r_fin:
                jugadas_activas.append(loteria["visible"])

    if not jugadas_activas:
        await message.answer("📵 No hay jugadas activas en este momento.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=nombre, callback_data=f"multi_{nombre}")]
            for nombre in jugadas_activas
        ]
    )

    await message.answer(
        "Selecciona la jugada que deseas consultar:",
        reply_markup=keyboard
    )

# =========================================================
# CALLBACK /multi
# =========================================================

@router.callback_query(lambda c: c.data.startswith("multi_"))
async def handle_multi(callback: types.CallbackQuery):
    global MENSAJE_FIJO_ID, ULTIMA_EJECUCION_GLOBAL

    await callback.answer()

    chat_origen = callback.message.chat.id
    if not grupo_permitido(chat_origen):
        return

    ahora_ts = datetime.now().timestamp()
    ahora = datetime.now(ZoneInfo("America/Caracas"))

    if ahora_ts - ULTIMA_EJECUCION_GLOBAL < COOLDOWN_GLOBAL:
        await callback.answer("⚠️ Procesando… intenta nuevamente en un momento.")
        return

    ULTIMA_EJECUCION_GLOBAL = ahora_ts

    datos = cargar_json_remoto()

    nombre_loteria = callback.data.replace("multi_", "")

    loteria_obj = None
    for loteria in datos["loterias"]:
        if loteria["visible"] == nombre_loteria:
            loteria_obj = loteria
            break

    if not loteria_obj:
        await callback.answer(f"❌ Lotería no encontrada: {nombre_loteria}", show_alert=True)
        return

    jugada_final = None

    for ventana in loteria_obj["ventanas"]:
        a_inicio = datetime.strptime(ventana["activar_inicio"], "%H:%M").time()
        r_fin = datetime.strptime(ventana["rango_fin"], "%H:%M").time()

        if a_inicio <= ahora.time() <= r_fin:
            jugada_final = ventana
            break

    if not jugada_final:
        for ventana in loteria_obj["ventanas"]:
            r_inicio = datetime.strptime(ventana["rango_inicio"], "%H:%M").time()
            r_fin = datetime.strptime(ventana["rango_fin"], "%H:%M").time()
            if r_inicio <= ahora.time() <= r_fin:
                jugada_final = ventana
                break

    chat_destino = chat_origen

    if not jugada_final:
        mensaje = (
            f"📵 *No hay jugada disponible en este momento*\n"
            f"Para la lotería consultada: *{md_escape(nombre_loteria)}*"
        )

        if MENSAJE_FIJO_ID:
            try:
                await bot.delete_message(chat_destino, MENSAJE_FIJO_ID)
            except:
                pass

        msg = await bot.send_message(
            chat_destino,
            mensaje,
            parse_mode="MarkdownV2"
        )

        MENSAJE_FIJO_ID = msg.message_id
        return

    jugada = [md_escape(j) for j in jugada_final["jugada"]]
    jugada_texto = " \\- ".join([f"*{j}*" for j in jugada])

    favorito_num, favorito_nombre = obtener_favorito(jugada_final["jugada"])
    favorito_texto = (
        f"*{md_escape(favorito_num)}*"
        if not favorito_nombre
        else f"*{md_escape(favorito_num)} \\({md_escape(favorito_nombre)}\\)*"
    )

    rango_dinamico = ajustar_rango_dinamico(
        jugada_final["rango_inicio"],
        jugada_final["rango_fin"],
        ahora
    )

    mensaje = (
        f"🔥 *{md_escape(nombre_loteria)}* 🔥\n"
        f"📅 *Actualización:* `{ahora.strftime('%I:%M %p')}`\n\n"
        f"🕒 *Sorteo:* `{rango_dinamico}`\n"
        f"🐾 *Favorito:* {favorito_texto}\n\n"
        f"🔢 *Jugada:* {jugada_texto}"
    )

    if MENSAJE_FIJO_ID:
        try:
            await bot.delete_message(chat_destino, MENSAJE_FIJO_ID)
        except:
            pass

    msg = await bot.send_message(
        chat_destino,
        mensaje,
        parse_mode="MarkdownV2"
    )

    MENSAJE_FIJO_ID = msg.message_id

# =========================================================
# /simular
# =========================================================

@router.message(Command("simular"))
async def simular(message: types.Message):
    if not grupo_permitido(message.chat.id):
        return

    ahora = datetime.now(ZoneInfo("America/Caracas"))

    jugada_simulada = ["12", "34", "56"]
    favorito_num = jugada_simulada[0]
    favorito_nombre = None

    if "Lotto Activo" in DICCIONARIO:
        favorito_nombre = DICCIONARIO["Lotto Activo"].get(favorito_num)

    favorito_texto = (
        f"*{md_escape(favorito_num)}*"
        if not favorito_nombre
        else f"*{md_escape(favorito_num)} \\({md_escape(favorito_nombre)}\\)*"
    )

    jugada_texto = " \\- ".join([f"*{md_escape(j)}*" for j in jugada_simulada])

    mensaje = (
        "🧪 *SIMULACIÓN DE JUGADA* 🧪\n"
        f"📅 *Hora:* `{ahora.strftime('%I:%M %p')}`\n\n"
        "🎯 *Lotería:* *Simulación Interna*\n"
        "🕒 *Sorteo:* `Simulado`\n"
        f"🐾 *Favorito:* {favorito_texto}\n\n"
        "🔢 *Jugada simulada:*\n"
        f"{jugada_texto}"
    )

    await message.answer(
        mensaje,
        parse_mode="MarkdownV2"
    )

# =========================================================
# /id y /reset
# =========================================================

@router.message(Command("id"))
async def get_id(message: types.Message):
    await message.answer(f"Chat ID: {message.chat.id}")

@router.message(Command("reset"))
async def reset(message: types.Message):
    global MENSAJE_FIJO_ID
    MENSAJE_FIJO_ID = None
    await message.answer("Reiniciado. Mensaje fijo limpiado.")

# =========================================================
# MAIN
# =========================================================

async def main():
    cargar_modo_test()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
