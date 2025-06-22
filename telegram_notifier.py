import requests
import logging
import threading
import time

class TelegramNotifier:
    def __init__(self, token, chat_id, bot_instance=None):
        self.token = token
        self.chat_id = chat_id
        self.bot_instance = bot_instance
        self.last_update_id = 0
        if bot_instance:
            self.command_thread = threading.Thread(target=self.command_listener, daemon=True)
            self.command_thread.start()

    def send_message(self, message, chat_id=None):
        chat_id = chat_id or self.chat_id
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logging.warning(f"Telegram message failed: {e}")

    def command_listener(self):
        while True:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates?offset={self.last_update_id+1}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                for update in data.get('result', []):
                    self.last_update_id = update['update_id']
                    if 'message' in update and 'text' in update['message']:
                        self.process_command(update['message'])
            except Exception as e:
                logging.error(f"Telegram command error: {e}")
            time.sleep(3)

    def process_command(self, message):
        command = message['text'].lower()
        chat_id = message['chat']['id']

        if command == '/status':
            self.handle_status_command(chat_id)
        elif command == '/pause':
            self.handle_pause_command(chat_id)
        elif command == '/resume':
            self.handle_resume_command(chat_id)
        elif command == '/positions':
            self.handle_positions_command(chat_id)
        elif command.startswith('/risk'):
            try:
                risk_val = float(command.split()[1])
                self.handle_risk_command(chat_id, risk_val)
            except:
                self.send_message("Invalid risk value. Usage: /risk 0.02", chat_id)
        elif command == '/help':
            self.handle_help_command(chat_id)

    def handle_status_command(self, chat_id):
        if self.bot_instance:
            account_info = self.bot_instance.mt5_manager.get_account_info()
            status = (f"Equity: ${account_info.equity:.2f}\n"
                      f"Balance: ${account_info.balance:.2f}\n"
                      f"Trading: {'ACTIVE' if self.bot_instance.trading_enabled else 'PAUSED'}")
            self.send_message(status, chat_id)

    def handle_pause_command(self, chat_id):
        if self.bot_instance:
            self.bot_instance.trading_enabled = False
            self.send_message("Trading PAUSED", chat_id)

    def handle_resume_command(self, chat_id):
        if self.bot_instance:
            self.bot_instance.trading_enabled = True
            self.send_message("Trading RESUMED", chat_id)

    def handle_positions_command(self, chat_id):
        if self.bot_instance:
            positions = self.bot_instance.mt5_manager.positions_get()
            if not positions:
                self.send_message("No open positions", chat_id)
                return
            msg = "Open Positions:\n"
            for pos in positions:
                pos_type = "BUY" if pos.type == 0 else "SELL"
                msg += f"{pos.symbol} {pos_type} {pos.volume} lots\n"
            self.send_message(msg, chat_id)

    def handle_risk_command(self, chat_id, risk):
        if self.bot_instance:
            self.bot_instance.current_risk = min(risk, 0.03)
            self.send_message(f"Risk set to {risk*100:.1f}%", chat_id)

    def handle_help_command(self, chat_id):
        help_text = ("Available commands:\n"
                     "/status - Bot status\n"
                     "/pause - Pause trading\n"
                     "/resume - Resume trading\n"
                     "/positions - Show open positions\n"
                     "/risk 0.02 - Set risk percentage\n"
                     "/help - Show this help")
        self.send_message(help_text, chat_id)
