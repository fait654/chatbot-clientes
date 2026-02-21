import os
import telebot
import pandas as pd
from flask import Flask
from threading import Thread

# TOKEN desde Render
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

# Flask para mantener activo el servicio
app = Flask(__name__)

# Cargar Excel
df = pd.read_excel("clientes.xlsx")

# Convertir Cod Cliente a string para comparar
df["Cod Cliente"] = df["Cod Cliente"].astype(str)

# Página web de prueba
@app.route('/')
def home():
    return "Bot activo"

# Manejo de mensajes
@bot.message_handler(func=lambda message: True)
def responder(message):

    texto = message.text.strip()

    # Buscar cliente en Excel
    resultado = df[df["Cod Cliente"] == texto]

    if not resultado.empty:

        direccion = resultado.iloc[0]["Direccion"]
        coordenadas = resultado.iloc[0]["Coordenadas"]
        geoposicion = resultado.iloc[0]["Geoposicion"]

        respuesta = f"""
📦 Cliente: {texto}

📍 Dirección:
{direccion}

🧭 Coordenadas:
{coordenadas}

🗺 Ubicación:
{geoposicion}
"""

        bot.reply_to(message, respuesta)

    else:
        bot.reply_to(
            message,
            "❌ Código no encontrado.\nIngrese un código válido."
        )

# Ejecutar bot en hilo separado
def run_bot():
    bot.infinity_polling()

Thread(target=run_bot).start()

# Ejecutar servidor Flask
port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)