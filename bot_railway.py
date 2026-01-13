import telebot
from telebot import types
import json
import os
import time
from datetime import datetime
import logging

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== КОНФИГУРАЦИЯ =====
# Используем переменные окружения Railway
TOKEN = os.environ.get('BOT_TOKEN', '7833029282:AAEsIe3pamC2UpN3O8hQkiVVbYNBLCLAjxc')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '340480842'))

bot = telebot.TeleBot(TOKEN)

# Настройки бота
MAX_MAIN = 20
MAX_RESERVE = 10

# ===== ХРАНЕНИЕ ДАННЫХ В ПАМЯТИ (для Railway) =====
# В Railway лучше хранить в памяти, так как файловая система временная
training_data = {
    'main': [],
    'reserve': [],
    'time': '20:45',
    'date': datetime.now().strftime('%Y-%m-%d'),
    'place': 'Пехорка, вторник',
    'registration_open': True
}

def save_data():
    """Сохранение данных в файл (опционально)"""
    try:
        with open('/data/training_data.json', 'w') as f:
            json.dump(training_data, f)
    except:
        pass  # Игнорируем ошибки записи

def load_data():
    """Загрузка данных из файла"""
    try:
        with open('/data/training_data.json', 'r') as f:
            data = json.load(f)
            training_data.update(data)
    except:
        pass  # Если файла нет, используем значения по умолчанию

# Загружаем данные при старте
load_data()

# ===== КОМАНДА /start =====
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn1 = types.KeyboardButton("📝 Записаться")
    btn2 = types.KeyboardButton("👥 Список")
    btn3 = types.KeyboardButton("⏰ Расписание")
    btn4 = types.KeyboardButton("🚫 Отменить")
    btn5 = types.KeyboardButton("❓ Помощь")
    
    if message.from_user.id == ADMIN_ID:
        btn6 = types.KeyboardButton("👑 Админ")
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    else:
        markup.add(btn1, btn2, btn3, btn4, btn5)
    
    welcome_text = (
        f"🏋️‍♂️ *SportOrlovS Training Bot* (ОБЛАЧНЫЙ)\n\n"
        f"*Следующая тренировка:*\n"
        f"📅 {training_data['date']}\n"
        f"⏰ {training_data['time']}\n"
        f"📍 {training_data['place']}\n"
        f"👥 *Лимиты:* {MAX_MAIN} осн. + {MAX_RESERVE} рез.\n\n"
        f"Выберите действие:"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=markup,
        parse_mode='Markdown'
    )
    logger.info(f"Пользователь {message.from_user.id} начал работу")

# ===== ЗАПИСЬ НА ТРЕНИРОВКУ =====
@bot.message_handler(func=lambda m: m.text == "📝 Записаться")
def sign_up(message):
    if not training_data['registration_open']:
        bot.send_message(message.chat.id, "❌ Запись закрыта!")
        return
    
    user_id = message.from_user.id
    name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    username = message.from_user.username or ""
    
    # Проверяем, не записан ли уже
    for user in training_data["main"] + training_data["reserve"]:
        if user["id"] == user_id:
            bot.send_message(message.chat.id, "❌ Вы уже записаны!")
            return
    
    user_info = {
        "id": user_id,
        "name": name,
        "last_name": last_name,
        "username": username,
        "time": datetime.now().strftime('%H:%M')
    }
    
    if len(training_data["main"]) < MAX_MAIN:
        training_data["main"].append(user_info)
        position = len(training_data["main"])
        full_name = f"{name} {last_name}".strip()
        status = f"✅ {full_name}, вы в основном списке! (место {position}/{MAX_MAIN})"
        
    elif len(training_data["reserve"]) < MAX_RESERVE:
        training_data["reserve"].append(user_info)
        position = len(training_data["reserve"])
        full_name = f"{name} {last_name}".strip()
        status = f"⏳ {full_name}, вы в резерве! (место {position}/{MAX_RESERVE})"
    else:
        bot.send_message(message.chat.id, "❌ Все места заняты!")
        return
    
    save_data()
    
    confirmation = (
        f"{status}\n\n"
        f"📅 *Тренировка:*\n"
        f"▪️ Дата: {training_data['date']}\n"
        f"▪️ Время: {training_data['time']}\n"
        f"▪️ Место: {training_data['place']}\n\n"
        f"📊 *Статистика:*\n"
        f"▪️ Основной список: {len(training_data['main'])}/{MAX_MAIN}\n"
        f"▪️ Резерв: {len(training_data['reserve'])}/{MAX_RESERVE}"
    )
    
    bot.send_message(message.chat.id, confirmation, parse_mode='Markdown')
    logger.info(f"Пользователь {user_id} записался на тренировку")

# ===== СПИСОК УЧАСТНИКОВ =====
@bot.message_handler(func=lambda m: m.text == "👥 Список")
def show_list(message):
    text = (
        f"🏋️‍♂️ *ТРЕНИРОВКА {training_data['date']}*\n"
        f"⏰ *Время:* {training_data['time']}\n"
        f"📍 *Место:* {training_data['place']}\n\n"
    )
    
    text += f"✅ *Основной список ({len(training_data['main'])}/{MAX_MAIN}):*\n"
    if training_data["main"]:
        for i, user in enumerate(training_data["main"], 1):
            full_name = f"{user['name']} {user.get('last_name', '')}".strip()
            username = f"(@{user['username']})" if user['username'] else ""
            text += f"{i}. {full_name} {username}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n⏳ *Резерв ({len(training_data['reserve'])}/{MAX_RESERVE}):*\n"
    if training_data["reserve"]:
        for i, user in enumerate(training_data["reserve"], 1):
            full_name = f"{user['name']} {user.get('last_name', '')}".strip()
            username = f"(@{user['username']})" if user['username'] else ""
            text += f"{i}. {full_name} {username}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n📊 *Всего записано:* {len(training_data['main']) + len(training_data['reserve'])}"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ===== РАСПИСАНИЕ =====
@bot.message_handler(func=lambda m: m.text == "⏰ Расписание")
def show_schedule(message):
    schedule_text = (
        f"⏰ *РАСПИСАНИЕ ТРЕНИРОВОК*\n\n"
        f"*Ближайшая тренировка:*\n"
        f"📅 {training_data['date']}\n"
        f"⏰ {training_data['time']}\n"
        f"📍 {training_data['place']}\n\n"
        f"*Регулярное расписание:*\n"
        f"▪️ Вторник Пехорка: 20:45\n"
        f"▪️ Суббота Ляпкина: 09:00\n\n"
        f"*Администратор:* https://t.me/Serega1202"
    )
    bot.send_message(message.chat.id, schedule_text, parse_mode='Markdown')

# ===== ОСТАЛЬНЫЕ ФУНКЦИИ (упрощенные) =====
@bot.message_handler(func=lambda m: m.text == "🚫 Отменить")
def cancel_registration(message):
    user_id = message.from_user.id
    
    for i, user in enumerate(training_data["main"]):
        if user["id"] == user_id:
            training_data["main"].pop(i)
            save_data()
            bot.send_message(message.chat.id, "✅ Запись отменена!")
            return
    
    for i, user in enumerate(training_data["reserve"]):
        if user["id"] == user_id:
            training_data["reserve"].pop(i)
            save_data()
            bot.send_message(message.chat.id, "✅ Запись из резерва отменена!")
            return
    
    bot.send_message(message.chat.id, "❌ Вы не записаны")

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def show_help(message):
    help_text = (
        "❓ *ПОМОЩЬ*\n\n"
        "*Как пользоваться:*\n"
        "1. 📝 *Записаться* - добавиться в список\n"
        "2. 👥 *Список* - посмотреть участников\n"
        "3. ⏰ *Расписание* - узнать время и место\n"
        "4. 🚫 *Отменить* - отменить запись\n\n"
        "*Администратор:* https://t.me/Serega1202"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# ===== ЗАПУСК БОТА С ПЕРЕЗАПУСКОМ =====
def main():
    logger.info("=" * 60)
    logger.info("🏋️‍♂️ SPORTORLOVS BOT ЗАПУЩЕН НА RAILWAY")
    logger.info("🤖 Бот: @sportOrlovS_training_bot")
    logger.info("☁️  Режим: Облачный (Railway.app)")
    logger.info("=" * 60)
    
    while True:
        try:
            logger.info("Запуск polling...")
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            logger.info("Перезапуск через 10 секунд...")
            time.sleep(10)

if __name__ == '__main__':
    main()