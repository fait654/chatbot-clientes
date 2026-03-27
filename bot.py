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

# cargar excel
df = pd.read_excel("clientes.xlsx")
df["Cod Cliente"] = df["Cod Cliente"].astype(str)

# guardar estado de usuarios
estado_usuario = {}
datos_temporales = {}


# =========================
# MENU
# =========================

def menu_principal():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📍 Datos del Cliente")
    markup.row("📄 Factura")
    markup.row("📅 Factura por Cliente y Fecha")  # NUEVA OPCION
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
# BUSCAR PDF
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


# 🔥 NUEVA BUSQUEDA POR CLIENTE + FECHA
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
    # DATOS CLIENTE
    # =========================

    if texto == "📍 Datos del Cliente":
        estado_usuario[chat_id] = "esperando_codigo_datos"

        bot.send_message(chat_id, "Ingrese el código del cliente:")
        return


    # =========================
    # FACTURA POR NUMERO
    # =========================

    if texto == "📄 Factura":
        estado_usuario[chat_id] = "esperando_numero_factura"

        bot.send_message(
            chat_id,
            "Ingrese el número de factura:\nEjemplo: B101-117424"
        )
        return


    # =========================
    # NUEVA OPCION CLIENTE + FECHA
    # =========================

    if texto == "📅 Factura por Cliente y Fecha":
        estado_usuario[chat_id] = "esperando_codigo_cliente_factura"

        bot.send_message(
            chat_id,
            "Ingrese el código del cliente:"
        )
        return


    # =========================
    # GUARDAR CODIGO Y PEDIR FECHA
    # =========================

    if estado_usuario.get(chat_id) == "esperando_codigo_cliente_factura":

        datos_temporales[chat_id] = {"codigo": texto}

        estado_usuario[chat_id] = "esperando_fecha_factura"

        bot.send_message(
            chat_id,
            "Ahora ingrese la fecha de facturación:\nEjemplo: 15-01-2024"
        )
        return


    # =========================
    # PROCESAR CLIENTE + FECHA
    # =========================

    if estado_usuario.get(chat_id) == "esperando_fecha_factura":

        fecha = texto
        codigo = datos_temporales.get(chat_id, {}).get("codigo")

        bot.send_message(chat_id, "🔍 Buscando factura...")

        paginas = buscar_por_cliente_fecha(codigo, fecha)

        if paginas:

            nombre_archivo = f"factura_{codigo}_{fecha}"
            archivo = crear_pdf_resultado(paginas, nombre_archivo)

            with open(archivo, "rb") as f:
                bot.send_document(
                    chat_id,
                    f,
                    caption=f"📄 Factura\nCliente: {codigo}\nFecha: {fecha}"
                )

            os.remove(archivo)

        else:
            bot.send_message(
                chat_id,
                "❌ No se encontraron resultados con esos datos"
            )

        estado_usuario[chat_id] = None
        datos_temporales.pop(chat_id, None)

        volver_menu(chat_id)
        return


    # =========================
    # PROCESAR DATOS CLIENTE
    # =========================

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

            try:
                lat, lon = coordenadas.split(",")
                bot.send_location(chat_id, float(lat), float(lon))
            except:
                pass

        else:
            bot.send_message(chat_id, "❌ Código no encontrado")

        estado_usuario[chat_id] = None
        volver_menu(chat_id)
        return


    # =========================
    # FACTURA POR NUMERO
    # =========================

    if estado_usuario.get(chat_id) == "esperando_numero_factura":

        numero_factura = texto

        bot.send_message(chat_id, "🔍 Buscando factura...")

        paginas = buscar_paginas_pdf(numero_factura)

        if paginas:

            archivo = crear_pdf_resultado(paginas, f"factura_{numero_factura}")

            with open(archivo, "rb") as f:
                bot.send_document(
                    chat_id,
                    f,
                    caption=f"📄 Factura {numero_factura}"
                )

            os.remove(archivo)

        else:
            bot.send_message(chat_id, "❌ No se encontró esa factura")

        estado_usuario[chat_id] = None
        volver_menu(chat_id)
        return


    # =========================
    # DEFAULT
    # =========================

    bot.send_message(
        chat_id,
        "Selecciona una opción del menú:",
        reply_markup=menu_principal()
    )


# =========================
# EJECUTAR BOT
# =========================

def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=60)


Thread(target=run_bot).start()


# =========================
# EJECUTAR FLASK
# =========================

port = int(os.environ.get("PORT", 10000))

app.run(
    host="0.0.0.0",
    port=port
)