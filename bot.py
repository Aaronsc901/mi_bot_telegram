import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ============================
# CARGA DEL JSON
# ============================

with open("datos.json", "r", encoding="utf-8") as f:
    datos = json.load(f)

# ============================
# FUNCIÓN PRINCIPAL DE EVALUACIÓN
# ============================

def obtener_jugada_actual(loteria):
    ahora = datetime.now().time()

    for ventana in loteria["ventanas"]:
        # Convertir horas a objetos time
        a_inicio = datetime.strptime(ventana["activar_inicio"], "%H:%M").time()
        a_fin    = datetime.strptime(ventana["activar_fin"], "%H:%M").time()
        r_inicio = datetime.strptime(ventana["rango_inicio"], "%H:%M").time()
        r_fin    = datetime.strptime(ventana["rango_fin"], "%H:%M").time()

        # 🟩 1. Evaluación desde activar_inicio (botón tradicional)
        if a_inicio <= ahora <= a_fin:
            return {
                "estado": "activacion",
                "jugada": ventana["jugada"],
                "visible": loteria["visible"]
            }

        # 🟩 2. Evaluación del rango real (jugada en curso)
        if r_inicio <= ahora <= r_fin:
            return {
                "estado": "curso",
                "jugada": ventana["jugada"],
                "visible": loteria["visible"]
            }

    return None

# ============================
# COMANDO /tradicional
# ============================

async def tradicional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resultados = []

    for loteria in datos["loterias"]:
        jugada_info = obtener_jugada_actual(loteria)

        if jugada_info and jugada_info["estado"] == "activacion":
            resultados.append(f"🔵 {jugada_info['visible']}: {', '.join(jugada_info['jugada'])}")

    if resultados:
        await update.message.reply_text("\n".join(resultados))
    else:
        await update.message.reply_text("No hay jugadas activas en este momento.")

# ============================
# COMANDO /multi
# ============================

async def multi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    resultados = []

    for loteria in datos["loterias"]:
        jugada_info = obtener_jugada_actual(loteria)

        if jugada_info and jugada_info["estado"] == "curso":
            resultados.append(f"🟢 {jugada_info['visible']}: {', '.join(jugada_info['jugada'])}")

    if resultados:
        await update.message.reply_text("\n".join(resultados))
    else:
        await update.message.reply_text("No hay jugadas en curso en este momento.")

# ============================
# COMANDO /start
# ============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bienvenido, aaron. El bot está listo.")

# ============================
# MAIN
# ============================

def main():
    app = ApplicationBuilder().token("TU_TOKEN_AQUI").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tradicional", tradicional))
    app.add_handler(CommandHandler("multi", multi))

    # ❌ NO agregar simular
    # ❌ NO registrar simular
    # ❌ NO incluir función simular

    app.run_polling()

if __name__ == "__main__":
    main()
