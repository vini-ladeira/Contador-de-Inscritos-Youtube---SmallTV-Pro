import os
import sys
import json
import time
import threading
import webbrowser
from datetime import datetime
from tkinter import Tk, Label, Button, Text, Entry, Toplevel, END, Scrollbar, RIGHT, LEFT, BOTH, Frame
from PIL import Image, ImageTk, ImageDraw, ImageFont
import requests
from googleapiclient.discovery import build
import pystray
from PIL import Image as PILImage, ImageDraw

# ------------------------------
# BASE_DIR compatível com PyInstaller (JSONs externos)
# ------------------------------
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------
# ARQUIVOS
# ------------------------------
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
TEXTS_FILE = os.path.join(BASE_DIR, "texts.json")
BG_IMAGE_PATH = os.path.join(BASE_DIR, "BG_YT.jpg")
IMAGE_FILENAME = os.path.join(BASE_DIR, "image.jpg")
LOG_FILE = os.path.join(BASE_DIR, "telinha_yt_log.txt")
LOG_FILE_PATH = os.path.join(BASE_DIR, "log_yt.json")

# ------------------------------
# Inicialização mínima de arquivos
# ------------------------------
for file in [LOG_FILE, LOG_FILE_PATH, CONFIG_FILE, TEXTS_FILE]:
    if not os.path.exists(file):
        if file == CONFIG_FILE:
            with open(file, "w", encoding="utf-8") as f:
                json.dump({"API_KEY":"","CHANNEL_ID":"","DEVICE_IP":"192.168.0.69"}, f, indent=4)
        elif file == TEXTS_FILE:
            with open(file, "w", encoding="utf-8") as f:
                json.dump({
                    "app_title": "Youtube Subscriber Small TV Pro - GeekMagic",
                    "button_configurar": "Configurar",
                    "button_fechar": "Fechar aplicação",
                    "popup_title": "Configuração",
                    "popup_api_label": "Sua API Key",
                    "popup_channel_label": "Seu Channel ID",
                    "popup_ip_label": "IP do dispositivo",
                    "popup_texto_inscritos": "subscribers",
                    "popup_salvar": "Salvar",
                    "popup_cancelar": "Cancelar",
                    "link_instagram": "Instagram",
                    "link_github": "GitHub"
                }, f, indent=4)
        else:
            with open(file,"w", encoding="utf-8") as f:
                f.write("{}" if "json" in file else "=== Log iniciado ===\n")

# ------------------------------
# CARREGAR TEXTOS
# ------------------------------
def load_texts():
    with open(TEXTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

texts = load_texts()

# ------------------------------
# Configurações
# ------------------------------
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

config = load_config()
API_KEY = config.get("API_KEY")
CHANNEL_ID = config.get("CHANNEL_ID")
DEVICE_IP = config.get("DEVICE_IP", "192.168.0.69")
CHECK_INTERVAL = 60
API_COOLDOWN = 120
stop_thread = False
texto_inscritos = texts.get("popup_texto_inscritos","subscribers")

# ------------------------------
# LOG
# ------------------------------
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")

# ------------------------------
# API YOUTUBE
# ------------------------------
def consulta_api():
    try:
        youtube = build('youtube', 'v3', developerKey=API_KEY)
        request = youtube.channels().list(part='snippet,statistics', id=CHANNEL_ID)
        response = request.execute()
        channel_name = response['items'][0]['snippet']['title']
        subscriber_count = int(response['items'][0]['statistics']['subscriberCount'])
        return channel_name, subscriber_count
    except Exception as e:
        log(f"Erro API YouTube: {e}")
        return None, None

# ------------------------------
# JSON LOG
# ------------------------------
def carrega_log():
    with open(LOG_FILE_PATH, 'r', encoding="utf-8") as f:
        return json.load(f) if os.path.getsize(LOG_FILE_PATH) > 0 else {}

def salva_log(data):
    with open(LOG_FILE_PATH, 'w', encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ------------------------------
# IMAGEM
# ------------------------------
def create_image(width, height, channel_name, sub_count, texto_inscritos):
    try:
        background = Image.open(BG_IMAGE_PATH).convert("RGB")
    except:
        background = Image.new("RGB", (width, height), color=(0,0,0))
    background = background.resize((width, height))
    draw = ImageDraw.Draw(background)
    try:
        font_big = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    canal = channel_name
    numero = f"{sub_count:,}".replace(",", ".")
    legenda = texto_inscritos

    bbox_canal = draw.textbbox((0, 0), canal, font=font_small)
    canal_w = bbox_canal[2] - bbox_canal[0]
    canal_h = bbox_canal[3] - bbox_canal[1]
    bbox_numero = draw.textbbox((0, 0), numero, font=font_big)
    numero_w = bbox_numero[2] - bbox_numero[0]
    numero_h = bbox_numero[3] - bbox_numero[1]
    bbox_legenda = draw.textbbox((0, 0), legenda, font=font_small)
    legenda_w = bbox_legenda[2] - bbox_legenda[0]
    legenda_h = bbox_legenda[3] - bbox_legenda[1]

    espaco_linhas = 10
    espaco_bloco = 25
    deslocamento_y = 40
    total_h = canal_h + numero_h + legenda_h + espaco_linhas*2 + espaco_bloco
    start_y = (height - total_h) // 2 + deslocamento_y
    pos_canal = ((width - canal_w) // 2, start_y)
    draw.text(pos_canal, canal, fill="white", font=font_small)
    pos_numero = ((width - numero_w) // 2, start_y + canal_h + espaco_bloco)
    draw.text(pos_numero, numero, fill="white", font=font_big)
    pos_legenda = ((width - legenda_w) // 2, pos_numero[1] + numero_h + espaco_linhas)
    draw.text(pos_legenda, legenda, fill="white", font=font_small)
    return background

# ------------------------------
# UPLOAD E DEFINIÇÃO
# ------------------------------
def upload_image_to_device(filename):
    url = f"http://{DEVICE_IP}/doUpload?dir=/image/"
    try:
        with open(filename, 'rb') as file:
            files = {'file': ('image.jpg', file, 'image/jpeg')}
            requests.post(url, files=files, stream=True, timeout=10)
            log("Upload enviado (resposta ignorada).")
    except Exception as e:
        log(f"Erro upload imagem: {e}")

def set_image_on_device(image_name):
    url = f"http://{DEVICE_IP}/set?img=%2Fimage%2F{image_name}"
    try:
        requests.get(url, timeout=5)
        log("Imagem definida no dispositivo.")
    except Exception as e:
        log(f"Erro set imagem: {e}")

# ------------------------------
# LOOP PRINCIPAL EM THREAD
# ------------------------------
def main_loop():
    global stop_thread, texto_inscritos
    image_width, image_height = 240, 240
    log("Loop principal iniciado.")
    while not stop_thread:
        try:
            log_data = carrega_log()
            now = datetime.now()
            consultar_api = True
            if 'last_checked' in log_data:
                last_checked = datetime.strptime(log_data['last_checked'], '%Y-%m-%d %H:%M:%S')
                if (now - last_checked).total_seconds() < API_COOLDOWN:
                    consultar_api = False

            if consultar_api and API_KEY and CHANNEL_ID:
                channel_name, subscriber_count = consulta_api()
                if channel_name is None:
                    log("Falha na API, usando dados anteriores")
                    channel_name = log_data.get('channel_name', 'Canal')
                    subscriber_count = log_data.get('cached_count', 0)
                log_data['cached_count'] = subscriber_count
                log_data['channel_name'] = channel_name
                log_data['last_checked'] = now.strftime('%Y-%m-%d %H:%M:%S')
                salva_log(log_data)
            else:
                channel_name = log_data.get('channel_name', 'Canal')
                subscriber_count = log_data.get('cached_count', 0)

            if subscriber_count != log_data.get('last_checked_count', 0):
                log(f"Alteração detectada: {log_data.get('last_checked_count',0)} → {subscriber_count}")
                image = create_image(image_width, image_height, channel_name, subscriber_count, texto_inscritos)
                image.save(IMAGE_FILENAME)
                upload_image_to_device(IMAGE_FILENAME)
                set_image_on_device(os.path.basename(IMAGE_FILENAME))
                log_data['last_checked_count'] = subscriber_count
                salva_log(log_data)
            else:
                log("Nenhuma alteração nos inscritos.")
        except Exception as e:
            log(f"Erro geral no loop: {e}")
        time.sleep(CHECK_INTERVAL)

# ------------------------------
# TRAY ICON
# ------------------------------
def create_tray_icon():
    icon_img = PILImage.new("RGB", (64, 64), color=(0, 0, 0))
    draw = ImageDraw.Draw(icon_img)
    draw.rectangle([16,16,48,48], fill="white")

    def on_quit(icon, item):
        close_app()
        icon.stop()

    def on_open(icon, item):
        root.deiconify()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir janela", on_open),
        pystray.MenuItem("Fechar aplicação", on_quit)
    )

    tray_icon = pystray.Icon("Youtube Small TV", icon_img, "Youtube Subscriber", menu)
    tray_icon.run()

def minimize_to_tray():
    root.withdraw()
    threading.Thread(target=create_tray_icon, daemon=True).start()

# ------------------------------
# INTERFACE
# ------------------------------
def create_ui():
    global root, API_KEY, CHANNEL_ID, DEVICE_IP, texto_inscritos, texts
    texts = load_texts()  # Sempre carregar ao iniciar
    root = Tk()
    root.title(texts["app_title"])
    root.geometry("900x500")
    root.protocol("WM_DELETE_WINDOW", minimize_to_tray)
    root.bind("<Unmap>", lambda e: minimize_to_tray() if root.state()=="iconic" else None)

    # Frames
    left_frame = Frame(root, width=450)
    left_frame.pack(side=LEFT, fill=BOTH, expand=True)
    right_frame = Frame(root, width=450)
    right_frame.pack(side=RIGHT, fill=BOTH, expand=True)

    # Log no frame esquerdo
    log_text = Text(left_frame)
    log_text.pack(fill=BOTH, expand=True)
    scrollbar = Scrollbar(log_text)
    scrollbar.pack(side=RIGHT, fill='y')
    log_text.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=log_text.yview)

    # Preview da imagem + botões no frame direito
    img_label = Label(right_frame)
    img_label.pack()
    btn_frame = Frame(right_frame)
    btn_frame.pack(pady=5)

    def open_config():
        popup = Toplevel(root)
        popup.title(texts["popup_title"])
        Label(popup, text=texts["popup_api_label"]).pack()
        api_entry = Entry(popup, width=50)
        api_entry.insert(0, API_KEY)
        api_entry.pack()
        Label(popup, text=texts["popup_channel_label"]).pack()
        channel_entry = Entry(popup, width=50)
        channel_entry.insert(0, CHANNEL_ID)
        channel_entry.pack()
        Label(popup, text=texts["popup_ip_label"]).pack()
        ip_entry = Entry(popup, width=50)
        ip_entry.insert(0, DEVICE_IP)
        ip_entry.pack()
        Label(popup, text="Texto inscritos").pack()
        inscritos_entry = Entry(popup, width=50)
        inscritos_entry.insert(0, texto_inscritos)
        inscritos_entry.pack()

        def save_config_popup():
            nonlocal popup
            global API_KEY, CHANNEL_ID, DEVICE_IP, texto_inscritos
            API_KEY = api_entry.get()
            CHANNEL_ID = channel_entry.get()
            DEVICE_IP = ip_entry.get()
            texto_inscritos = inscritos_entry.get()[:13]  # Limite 13 caracteres
            config["API_KEY"] = API_KEY
            config["CHANNEL_ID"] = CHANNEL_ID
            config["DEVICE_IP"] = DEVICE_IP
            save_config(config)
            # Atualiza a imagem imediatamente
            log_data = carrega_log()
            channel_name = log_data.get('channel_name', 'Canal')
            subscriber_count = log_data.get('cached_count', 0)
            image = create_image(240,240,channel_name,subscriber_count,texto_inscritos)
            image.save(IMAGE_FILENAME)
            upload_image_to_device(IMAGE_FILENAME)
            set_image_on_device(os.path.basename(IMAGE_FILENAME))
            popup.destroy()

        Button(popup, text=texts["popup_salvar"], command=save_config_popup).pack(side=LEFT, padx=5, pady=5)
        Button(popup, text=texts["popup_cancelar"], command=popup.destroy).pack(side=RIGHT, padx=5, pady=5)

    Button(btn_frame, text=texts["button_configurar"], command=open_config).pack(side=LEFT, padx=5)
    Button(btn_frame, text=texts["button_fechar"], command=lambda: close_app()).pack(side=RIGHT, padx=5)

    # Links centralizados no frame direito
    link_frame = Frame(right_frame)
    link_frame.pack(side='bottom', fill='x', pady=5)
    container = Frame(link_frame)
    container.pack()
    instagram_link = Label(container, text=texts["link_instagram"], fg="blue", cursor="hand2")
    instagram_link.pack(side=LEFT, padx=(0,25))
    github_link = Label(container, text=texts["link_github"], fg="blue", cursor="hand2")
    github_link.pack(side=LEFT, padx=(25,0))
    instagram_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.instagram.com/vini_ladeira/"))
    github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/vini-ladeira"))

    # Atualização UI
    def update_ui():
        if os.path.exists(IMAGE_FILENAME):
            img = Image.open(IMAGE_FILENAME).resize((240,240))
            img_tk = ImageTk.PhotoImage(img)
            img_label.img_tk = img_tk
            img_label.config(image=img_tk)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE,'r',encoding='utf-8') as f:
                linhas = f.readlines()
                linhas.reverse()
                log_text.delete(1.0, END)
                log_text.insert(END, "".join(linhas))
        root.after(2000, update_ui)

    update_ui()
    root.mainloop()

def close_app():
    global stop_thread
    stop_thread = True
    root.destroy()

# ------------------------------
# EXECUÇÃO
# ------------------------------
threading.Thread(target=main_loop, daemon=True).start()
create_ui()
