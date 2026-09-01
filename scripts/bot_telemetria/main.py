"""
Punto de Entrada Principal — Bot de Telemetría y Despacho Sanesca
Polling en tiempo real de Telegram + Programación Automática Matutina y Pre-Alerta
"""
import time
import sys
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_CHAT_ID, validate_config
from telegram_handlers import (
    handle_text_message, handle_callback_query, register_bot_commands
)
from scheduler import scheduler

sys.stdout.reconfigure(encoding='utf-8')
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def start_bot_polling():
    print("==================================================")
    print("⚡ SANESCA BOT TELEMETRÍA & SUITE OPERATIVA C2")
    print("🤖 Conectado a @SanescaAIBot")
    print(f"👤 Administrador Autorizado: ID {TELEGRAM_AUTHORIZED_CHAT_ID}")
    print("⏰ Programador Matutino Activo: 06:30 AM (UTC-4)")
    print("🔔 Pre-Alerta Dinámica Activa: 25 min antes del corte")
    print("==================================================\n")

    errors = validate_config(require_whatsapp=False)
    if errors:
        for err in errors:
            print(f"⚠️ {err}")
        print()

    # Registrar menú nativo de comandos en Telegram
    cmd_ok = register_bot_commands()
    if cmd_ok:
        print("✅ Menú de comandos nativo [/] registrado con éxito en Telegram.")

    last_offset = 0

    # Obtener último offset para no procesar mensajes viejos
    try:
        r = requests.get(f"{BASE_URL}/getUpdates?offset=-1", timeout=10)
        res = r.json()
        if res.get("ok") and res.get("result"):
            last_offset = res["result"][-1]["update_id"] + 1
    except Exception as e:
        print(f"Error inicializando offset: {e}")

    print("🟢 Escuchando comandos en Telegram (Presiona Ctrl+C para salir)...\n")

    while True:
        try:
            # 1. Verificar alertas automáticas (06:30 AM y Pre-Alerta)
            scheduler.check_and_execute()

            # 2. Polling de mensajes y botones de Telegram
            url = f"{BASE_URL}/getUpdates?offset={last_offset}&timeout=20"
            r = requests.get(url, timeout=25)

            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        last_offset = update["update_id"] + 1

                        # Manejar mensajes de texto
                        if "message" in update and "text" in update["message"]:
                            msg = update["message"]
                            chat_id = msg["chat"]["id"]
                            text = msg["text"]
                            user_name = msg["from"].get("first_name", "")
                            print(f"📨 [Telegram] Mensaje de {user_name} ({chat_id}): {text}")
                            handle_text_message(chat_id, text, user_name)

                        # Manejar clics de botones inline
                        elif "callback_query" in update:
                            cb = update["callback_query"]
                            user_name = cb["from"].get("first_name", "")
                            data_action = cb.get("data", "")
                            print(f"🔘 [Telegram] Botón presionado por {user_name}: {data_action}")
                            handle_callback_query(cb)

            elif r.status_code != 200:
                print(f"⚠️ Telegram API HTTP {r.status_code}. Reintentando...")
                time.sleep(3)

        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError:
            print("⚠️ Error de red. Reintentando en 5 segundos...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n🛑 Servicio detenido manualmente por el usuario.")
            break
        except Exception as e:
            print(f"❌ Error inesperado en el ciclo principal: {e}")
            time.sleep(3)

if __name__ == "__main__":
    start_bot_polling()
