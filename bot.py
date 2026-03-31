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
df["Cod Cliente"] = df["Cod Cliente"].astype(str)

# =========================
# EXCEL ESTADOS
# =========================

df_estados = pd.read_excel("estados.xlsx")

# limpiar texto
df_estados["VENDEDOR"] = df_estados["VENDEDOR"].astype(str).str.upper().str.strip()
df_estados["ESTADO"] = df_estados["ESTADO"].astype(str).str.upper().str.strip()

# 🔥 LIMPIEZA PRO DE MONTO (SOLUCION DEFINITIVA)
df_estados["MONTO"] = (
    df_estados["MONTO"]
    .astype(str)
    .str.replace("S/.", "", regex=False)
    .str.replace("S/", "", regex=False)
    .str.replace(" ", "", regex=False)
)

# detectar formato europeo y convertir
df_estados["MONTO"] = df_estados["MONTO"].str.replace(",", ".", regex=False)

# convertir a número seguro
df_estados["MONTO"] = pd.to_numeric(df_estados["MONTO"], errors="coerce").fillna(0)

# =========================
# VARIABLES
# =========================

estado_usuario = {}
datos_temporales = {}

CLAVE = "123456"

# =========================
# MENU
# =========================

def menu_principal():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📍 Datos del Cliente")
    markup.row("📄 Factura")
    markup.row("📅 Factura por Cliente y Fecha")
    markup.row("📊 Estados del Cliente")
    return markup


def volver_menu(chat_id):
    bot.send_message(
        chat_id,
        "\n¿Qué deseas consultar ahora?",
        reply_markup=menu_principal()
    )

# =========================
# FLASK
# =========================

@app.route('/')
def home():
    return "Bot activo"

# =========================
# PDF FUNCIONES
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


def buscar_por_cliente_fecha(codigo, fecha):
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

                    if codigo in texto and fecha in texto:
                        paginas.append((ruta, i))

                doc.close()
            except:
                pass

    return paginas


def crear_pdf_resultado(paginas, nombre_base):
    nuevo = fitz.open()

    for ruta, pagina in paginas:
        doc = fitz.open(ruta)
        nuevo.insert_pdf(doc, from_page=pagina, to_page=pagina)
        doc.close()

    nombre = f"{nombre_base}.pdf"
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
        "Hola 👋 Bienvenido al sistema.\n\nSelecciona una opción:",
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
    # ESTADOS CLIENTE
    # =========================

    if texto == "📊 Estados del Cliente":
        estado_usuario[chat_id] = "esperando_clave_estados"
        bot.send_message(chat_id, "🔒 Ingrese la clave:")
        return

    if estado_usuario.get(chat_id) == "esperando_clave_estados":

        if texto == CLAVE:
            estado_usuario[chat_id] = "esperando_nombre_estados"
            bot.send_message(chat_id, "✅ Clave correcta\n\nIngrese nombre o apellido:")
        else:
            bot.send_message(chat_id, "❌ Clave incorrecta")
            estado_usuario[chat_id] = None
            volver_menu(chat_id)
        return

    if estado_usuario.get(chat_id) == "esperando_nombre_estados":

        nombre = texto.upper()

        filtro = df_estados["VENDEDOR"].str.contains(nombre, na=False)
        resultado = df_estados[filtro]

        if resultado.empty:
            bot.send_message(chat_id, "❌ No se encontraron resultados")
        else:

            cancelado = resultado[resultado["ESTADO"] == "CANCELADO"]["MONTO"].sum()
            pendiente = resultado[resultado["ESTADO"] == "PENDIENTE"]["MONTO"].sum()
            total = cancelado + pendiente

            respuesta = (
                f"📊 RESULTADO DEL CLIENTE\n\n"
                f"👤 Nombre buscado: {texto}\n\n"
                f"💰 Monto Cancelado: S/ {cancelado:,.2f}\n"
                f"⏳ Monto Pendiente: S/ {pendiente:,.2f}\n"
                f"🧾 Monto Total: S/ {total:,.2f}"
            )

            bot.send_message(chat_id, respuesta)

        estado_usuario[chat_id] = None
        volver_menu(chat_id)
        return

    # =========================
    # DATOS CLIENTE
    # =========================

    if texto == "📍 Datos del Cliente":
        estado_usuario[chat_id] = "esperando_codigo_datos"
        bot.send_message(chat_id, "Ingrese el código del cliente:")
        return

    if estado_usuario.get(chat_id) == "esperando_codigo_datos":

        codigo = texto
        resultado = df[df["Cod Cliente"] == codigo]

        if not resultado.empty:

            direccion = resultado.iloc[0]["Direccion"]
            coordenadas = resultado.iloc[0]["Coordenadas"]
            geoposicion = resultado.iloc[0]["Geoposicion"]

            respuesta = (
                f"📦 Cliente: {codigo}\n\n"
                f"📍 Dirección:\n{direccion}\n\n"
                f"🧭 Coordenadas:\n{coordenadas}\n\n"
                f"🗺 Geolocalización:\n{geoposicion}"
            )

            bot.send_message(chat_id, respuesta)

        else:
            bot.send_message(chat_id, "❌ Código no encontrado")

        estado_usuario[chat_id] = None
        volver_menu(chat_id)
        return

    # =========================
    # FACTURA
    # =========================

    if texto == "📄 Factura":
        estado_usuario[chat_id] = "esperando_numero_factura"
        bot.send_message(chat_id, "Ingrese el número de factura:")
        return

    if estado_usuario.get(chat_id) == "esperando_numero_factura":

        numero_factura = texto
        bot.send_message(chat_id, "🔍 Buscando factura...")

        paginas = buscar_paginas_pdf(numero_factura)

        if paginas:
            archivo = crear_pdf_resultado(paginas, f"factura_{numero_factura}")

            with open(archivo, "rb") as f:
                bot.send_document(chat_id, f)

            os.remove(archivo)
        else:
            bot.send_message(chat_id, "❌ No se encontró esa factura")

        estado_usuario[chat_id] = None
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
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

Thread(target=run_bot).start()

port = int(os.environ.get("PORT", 10000))

app.run(host="0.0.0.0", port=port)