import os
import telebot
import pandas as pd
import fitz
from flask import Flask
from threading import Thread

# =========================
# CONFIGURACION
# =========================

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

PDF_FOLDER = "pdfs"

# =========================
# EXCEL CLIENTES
# =========================

df = pd.read_excel("clientes.xlsx")
df["Cod Cliente"] = df["Cod Cliente"].astype(str).str.strip()

# =========================
# EXCEL ESTADOS
# =========================

df_estados = pd.read_excel("estados.xlsx")

df_estados["VENDEDOR"] = df_estados["VENDEDOR"].astype(str).str.upper().str.strip()
df_estados["ESTADO"] = df_estados["ESTADO"].astype(str).str.upper().str.strip()

df_estados["MONTO"] = (
    df_estados["MONTO"]
    .astype(str)
    .str.replace("S/.", "", regex=False)
    .str.replace("S/", "", regex=False)
    .str.replace(" ", "", regex=False)
)

df_estados["MONTO"] = df_estados["MONTO"].str.replace(",", ".", regex=False)
df_estados["MONTO"] = pd.to_numeric(df_estados["MONTO"], errors="coerce").fillna(0)

# =========================
# VARIABLES
# =========================

estado_usuario = {}
datos_temporales = {}

CLAVE = "3412"

# =========================
# MENU
# =========================

def menu_principal():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📍 Datos del Cliente")
    markup.row("📄 Factura")
    markup.row("📅 Factura por Cliente y Fecha")
    markup.row("📊 Bot Prueba")
    return markup


def volver_menu(chat_id):
    bot.send_message(chat_id, "¿Qué deseas consultar ahora?", reply_markup=menu_principal())

# =========================
# FLASK
# =========================

@app.route('/')
def home():
    return "Bot activo - BOT PRUEBA"

# =========================
# 🔥 FUNCION MEJORADA
# =========================

def normalizar_fecha(fecha):
    return fecha.replace("/", "-").replace(".", "-").strip()

def buscar_por_cliente_fecha(codigo, fecha):
    paginas = []

    codigo = str(codigo).strip()
    fecha = normalizar_fecha(fecha)

    if not os.path.exists(PDF_FOLDER):
        return paginas

    for archivo in os.listdir(PDF_FOLDER):
        if archivo.lower().endswith(".pdf"):
            ruta = os.path.join(PDF_FOLDER, archivo)

            try:
                doc = fitz.open(ruta)

                # 🔥 leer todo el PDF (MUCHO MÁS RÁPIDO)
                texto_total = ""
                for page in doc:
                    texto_total += page.get_text()

                texto_total = texto_total.replace("/", "-").replace(".", "-")

                # 🔥 validar rápido
                if codigo in texto_total and fecha in texto_total:

                    # 🔥 ahora sí buscar páginas exactas
                    for i in range(len(doc)):
                        texto = doc[i].get_text()
                        texto = texto.replace("/", "-").replace(".", "-")

                        if codigo in texto and fecha in texto:
                            paginas.append((ruta, i))

                doc.close()

            except:
                pass

    return paginas

# =========================
# FACTURA NORMAL
# =========================

def buscar_paginas_pdf(numero_factura):
    paginas = []

    if not os.path.exists(PDF_FOLDER):
        return paginas

    for archivo in os.listdir(PDF_FOLDER):
        if archivo.lower().endswith(".pdf"):
            ruta = os.path.join(PDF_FOLDER, archivo)

            try:
                doc = fitz.open(ruta)

                for i in range(len(doc)):
                    texto = doc[i].get_text()

                    if numero_factura in texto:
                        paginas.append((ruta, i))

                doc.close()
            except:
                pass

    return paginas

# =========================
# CREAR PDF
# =========================

def crear_pdf_resultado(paginas, nombre):
    nuevo = fitz.open()

    for ruta, pagina in paginas:
        doc = fitz.open(ruta)
        nuevo.insert_pdf(doc, from_page=pagina, to_page=pagina)
        doc.close()

    nuevo.save(nombre)
    nuevo.close()

    return nombre

# =========================
# START
# =========================

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    estado_usuario[chat_id] = None

    bot.send_message(
        chat_id,
        "🤖 BOT PRUEBA\n\nSelecciona una opción:",
        reply_markup=menu_principal()
    )

# =========================
# MENSAJES
# =========================

@bot.message_handler(func=lambda message: True)
def manejar_mensaje(message):

    chat_id = message.chat.id
    texto = message.text.strip()

    # =========================
    # ESTADOS
    # =========================

    if texto == "📊 Bot Prueba":
        estado_usuario[chat_id] = "clave"
        bot.send_message(chat_id, "🔒 Ingrese la clave:")
        return

    if estado_usuario.get(chat_id) == "clave":

        if texto == CLAVE:
            estado_usuario[chat_id] = "nombre"
            bot.send_message(chat_id, "Ingrese nombre o apellido:")
        else:
            bot.send_message(chat_id, "❌ Clave incorrecta")
            estado_usuario[chat_id] = None
            volver_menu(chat_id)
        return

    if estado_usuario.get(chat_id) == "nombre":

        nombre = texto.upper()
        resultado = df_estados[df_estados["VENDEDOR"].str.contains(nombre, na=False)]

        if resultado.empty:
            bot.send_message(chat_id, "❌ No se encontraron resultados")
        else:

            respuesta = "📊 RESULTADOS\n\n"

            for persona, grupo in resultado.groupby("VENDEDOR"):

                cancelado = grupo[grupo["ESTADO"] == "CANCELADO"]["MONTO"].sum()
                pendiente = grupo[grupo["ESTADO"] == "PENDIENTE"]["MONTO"].sum()
                total = cancelado + pendiente

                respuesta += (
                    f"👤 {persona}\n"
                    f"💰 Cancelado: S/ {cancelado:,.2f}\n"
                    f"⏳ Pendiente: S/ {pendiente:,.2f}\n"
                    f"🧾 Total: S/ {total:,.2f}\n\n"
                )

            bot.send_message(chat_id, respuesta)

        estado_usuario[chat_id] = None
        volver_menu(chat_id)
        return

    # =========================
    # FACTURA CLIENTE + FECHA
    # =========================

    if texto == "📅 Factura por Cliente y Fecha":
        estado_usuario[chat_id] = "codigo_cliente"
        bot.send_message(chat_id, "Ingrese el código del cliente:")
        return

    if estado_usuario.get(chat_id) == "codigo_cliente":
        datos_temporales[chat_id] = {"codigo": texto}
        estado_usuario[chat_id] = "fecha_cliente"
        bot.send_message(chat_id, "Ingrese la fecha (Ej: 28/03/2026):")
        return

    if estado_usuario.get(chat_id) == "fecha_cliente":

        codigo = datos_temporales[chat_id]["codigo"]
        fecha = texto

        bot.send_message(chat_id, "🔍 Buscando factura... (puede tardar unos segundos)")

        paginas = buscar_por_cliente_fecha(codigo, fecha)

        if paginas:
            archivo = crear_pdf_resultado(paginas, f"factura_{codigo}.pdf")

            with open(archivo, "rb") as f:
                bot.send_document(chat_id, f)

            os.remove(archivo)
        else:
            bot.send_message(chat_id, "❌ No se encontraron facturas con esa fecha")

        estado_usuario[chat_id] = None
        datos_temporales.pop(chat_id, None)
        volver_menu(chat_id)
        return

    # =========================
    # DEFAULT
    # =========================

    bot.send_message(chat_id, "Selecciona una opción:", reply_markup=menu_principal())

# =========================
# RUN
# =========================

def run_bot():
    bot.infinity_polling()

Thread(target=run_bot).start()

port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)