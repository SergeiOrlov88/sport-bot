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

# ===== КОНФИГУРАЦИЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
TOKEN = os.environ.get('BOT_TOKEN', '7833029282:AAEsIe3pamC2UpN3O8hQkiVVbYNBLCLAjxc')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '340480842'))

# ===== РЕЖИМ РАБОТЫ =====
# Для Railway ставим False - рабочий режим
TEST_MODE = os.environ.get('TEST_MODE', 'False').lower() == 'true'

if TEST_MODE:
    MAX_MAIN = 3      # Тестовый режим
    MAX_RESERVE = 2
    MODE_TEXT = "ТЕСТОВЫЙ РЕЖИМ"
else:
    MAX_MAIN = 20     # Рабочий режим
    MAX_RESERVE = 10
    MODE_TEXT = "РАБОЧИЙ РЕЖИМ"

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "/data/training_data.json"  # В Railway лучше хранить в /data

# ===== ХРАНЕНИЕ ДАННЫХ =====
def load_data():
    """Загрузка данных из файла"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Проверяем обязательные поля
                required_fields = {
                    'main': [],
                    'reserve': [],
                    'time': '20:45',
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'place': 'Пехорка, вторник',
                    'registration_open': True
                }
                
                for field, default_value in required_fields.items():
                    if field not in data:
                        data[field] = default_value
                
                return data
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
    
    # Если файла нет или ошибка - создаем новый
    return create_default_data()

def create_default_data():
    """Создание данных по умолчанию"""
    default_data = {
        'main': [],
        'reserve': [],
        'time': '20:45',
        'date': datetime.now().strftime('%Y-%m-%d'),
        'place': 'Пехорка, вторник',
        'registration_open': True
    }
    save_data(default_data)
    return default_data

def save_data(data):
    """Сохранение данных"""
    try:
        # Создаем папку /data если её нет
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

def is_admin(user_id):
    return user_id == ADMIN_ID

def format_user_name(user):
    """Форматирование имени с фамилией"""
    name = user.get('name', '')
    last_name = user.get('last_name', '')
    
    if last_name:
        return f"{name} {last_name}"
    return name

# ===== КОМАНДА /start =====
@bot.message_handler(commands=['start'])
def start(message):
    data = load_data()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn1 = types.KeyboardButton("📝 Записаться")
    btn2 = types.KeyboardButton("👥 Список")
    btn3 = types.KeyboardButton("⏰ Расписание")
    btn4 = types.KeyboardButton("🚫 Отменить")
    btn5 = types.KeyboardButton("❓ Помощь")
    
    if is_admin(message.from_user.id):
        btn6 = types.KeyboardButton("👑 Админ")
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    else:
        markup.add(btn1, btn2, btn3, btn4, btn5)
    
    welcome_text = (
        f"🏋️‍♂️ *SportOrlovS Training Bot* ({MODE_TEXT})\n\n"
        f"*Следующая тренировка:*\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}\n"
        f"📍 {data['place']}\n"
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
    data = load_data()
    
    if not data['registration_open']:
        bot.send_message(message.chat.id, "❌ Запись закрыта!")
        return
    
    user_id = message.from_user.id
    name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    username = message.from_user.username or ""
    
    # Проверяем, не записан ли уже
    for user in data["main"] + data["reserve"]:
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
    
    if len(data["main"]) < MAX_MAIN:
        data["main"].append(user_info)
        position = len(data["main"])
        full_name = f"{name} {last_name}".strip()
        status = f"✅ {full_name}, вы в основном списке! (место {position}/{MAX_MAIN})"
        
    elif len(data["reserve"]) < MAX_RESERVE:
        data["reserve"].append(user_info)
        position = len(data["reserve"])
        full_name = f"{name} {last_name}".strip()
        status = f"⏳ {full_name}, вы в резерве! (место {position}/{MAX_RESERVE})"
    else:
        bot.send_message(message.chat.id, "❌ Все места заняты!")
        return
    
    save_data(data)
    
    # Отправляем подтверждение
    confirmation = (
        f"{status}\n\n"
        f"📅 *Тренировка:*\n"
        f"▪️ Дата: {data['date']}\n"
        f"▪️ Время: {data['time']}\n"
        f"▪️ Место: {data['place']}\n\n"
        f"📊 *Статистика:*\n"
        f"▪️ Основной список: {len(data['main'])}/{MAX_MAIN}\n"
        f"▪️ Резерв: {len(data['reserve'])}/{MAX_RESERVE}"
    )
    
    bot.send_message(message.chat.id, confirmation, parse_mode='Markdown')
    logger.info(f"Пользователь {user_id} записался на тренировку")

# ===== СПИСОК УЧАСТНИКОВ =====
@bot.message_handler(func=lambda m: m.text == "👥 Список")
def show_list(message):
    data = load_data()
    
    text = (
        f"🏋️‍♂️ *ТРЕНИРОВКА {data['date']}* ({MODE_TEXT})\n"
        f"⏰ *Время:* {data['time']}\n"
        f"📍 *Место:* {data['place']}\n"
        f"👥 *Лимиты:* {MAX_MAIN}+{MAX_RESERVE}\n\n"
    )
    
    text += f"✅ *Основной список ({len(data['main'])}/{MAX_MAIN}):*\n"
    if data["main"]:
        for i, user in enumerate(data["main"], 1):
            full_name = format_user_name(user)
            username = f"(@{user['username']})" if user['username'] else ""
            time_str = f" - {user.get('time', '')}" if user.get('time') else ""
            text += f"{i}. {full_name} {username}{time_str}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n⏳ *Резерв ({len(data['reserve'])}/{MAX_RESERVE}):*\n"
    if data["reserve"]:
        for i, user in enumerate(data["reserve"], 1):
            full_name = format_user_name(user)
            username = f"(@{user['username']})" if user['username'] else ""
            time_str = f" - {user.get('time', '')}" if user.get('time') else ""
            text += f"{i}. {full_name} {username}{time_str}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n📊 *Всего записано:* {len(data['main']) + len(data['reserve'])}"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ===== ОТМЕНА ЗАПИСИ С ПЕРЕВОДОМ ИЗ РЕЗЕРВА =====
@bot.message_handler(func=lambda m: m.text == "🚫 Отменить")
def cancel_registration(message):
    data = load_data()
    user_id = message.from_user.id
    
    # Ищем в основном списке
    for i, user in enumerate(data["main"]):
        if user["id"] == user_id:
            removed_user = data["main"].pop(i)
            removed_name = format_user_name(removed_user)
            
            # Если есть резерв, переводим первого
            if data["reserve"]:
                first_reserve = data["reserve"].pop(0)
                data["main"].append(first_reserve)
                promoted_name = format_user_name(first_reserve)
                
                try:
                    bot.send_message(
                        first_reserve["id"],
                        f"🎉 *{promoted_name}, вы переведены в основной список!*\n\n"
                        f"📅 Тренировка: {data['date']}\n"
                        f"⏰ Время: {data['time']}\n"
                        f"📍 Место: {data['place']}"
                    )
                    logger.info(f"Уведомление отправлено: {promoted_name}")
                except Exception as e:
                    logger.error(f"Не удалось уведомить: {e}")
                
                save_data(data)
                bot.send_message(
                    message.chat.id,
                    f"✅ *{removed_name}, ваша запись отменена!*\n\n"
                    f"🔄 *{promoted_name} переведен из резерва в основной список.*"
                )
            else:
                save_data(data)
                bot.send_message(
                    message.chat.id,
                    f"✅ *{removed_name}, ваша запись отменена!*"
                )
            return
    
    # Ищем в резерве
    for i, user in enumerate(data["reserve"]):
        if user["id"] == user_id:
            removed_user = data["reserve"].pop(i)
            removed_name = format_user_name(removed_user)
            save_data(data)
            
            bot.send_message(
                message.chat.id,
                f"✅ *{removed_name}, ваша запись из резерва отменена!*"
            )
            return
    
    bot.send_message(message.chat.id, "❌ Вы не записаны на тренировку")

# ===== АДМИН-ПАНЕЛЬ =====
@bot.message_handler(func=lambda m: m.text == "👑 Админ" and is_admin(m.from_user.id))
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn1 = types.InlineKeyboardButton("⏰ Изменить время", callback_data='admin_set_time')
    btn2 = types.InlineKeyboardButton("📅 Изменить дату", callback_data='admin_set_date')
    btn3 = types.InlineKeyboardButton("📍 Изменить место", callback_data='admin_set_place')
    btn4 = types.InlineKeyboardButton("🔄 Новая тренировка", callback_data='admin_new_training')
    btn5 = types.InlineKeyboardButton("🔓 Открыть запись", callback_data='admin_open_reg')
    btn6 = types.InlineKeyboardButton("🔒 Закрыть запись", callback_data='admin_close_reg')
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    data = load_data()
    
    admin_text = (
        f"👑 *АДМИН-ПАНЕЛЬ* ({MODE_TEXT})\n\n"
        f"*Текущая тренировка:*\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}\n"
        f"📍 Место: {data['place']}\n"
        f"👥 Участников: {len(data['main'])}/{MAX_MAIN}\n"
        f"⏳ Резерв: {len(data['reserve'])}/{MAX_RESERVE}\n"
        f"📝 Запись: {'открыта ✅' if data['registration_open'] else 'закрыта ❌'}"
    )
    
    bot.send_message(
        message.chat.id,
        admin_text,
        reply_markup=markup,
        parse_mode='Markdown'
    )

# ===== ОБРАБОТКА АДМИН-КОМАНД =====
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback_handler(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Нет доступа!")
        return
    
    data = load_data()
    
    if call.data == 'admin_set_time':
        msg = bot.send_message(call.message.chat.id, "⏰ Введите новое время (например: 20:45):")
        bot.register_next_step_handler(msg, lambda m: process_admin_command(m, 'time'))
    
    elif call.data == 'admin_set_date':
        msg = bot.send_message(call.message.chat.id, "📅 Введите новую дату (формат: ГГГГ-ММ-ДД):")
        bot.register_next_step_handler(msg, lambda m: process_admin_command(m, 'date'))
    
    elif call.data == 'admin_set_place':
        msg = bot.send_message(call.message.chat.id, "📍 Введите новое место тренировки:")
        bot.register_next_step_handler(msg, lambda m: process_admin_command(m, 'place'))
    
    elif call.data == 'admin_new_training':
        new_data = create_default_data()
        bot.send_message(call.message.chat.id, "🔄 Создана новая тренировка! Списки очищены.", parse_mode='Markdown')
    
    elif call.data == 'admin_open_reg':
        data['registration_open'] = True
        save_data(data)
        bot.send_message(call.message.chat.id, "🔓 Запись открыта!", parse_mode='Markdown')
    
    elif call.data == 'admin_close_reg':
        data['registration_open'] = False
        save_data(data)
        bot.send_message(call.message.chat.id, "🔒 Запись закрыта!", parse_mode='Markdown')
    
    bot.answer_callback_query(call.id)

def process_admin_command(message, command_type):
    if not is_admin(message.from_user.id):
        return
    
    data = load_data()
    
    if command_type == 'time':
        new_time = message.text.strip()
        data['time'] = new_time
        save_data(data)
        bot.send_message(message.chat.id, f"✅ Время изменено на *{new_time}*", parse_mode='Markdown')
    
    elif command_type == 'date':
        new_date = message.text.strip()
        try:
            datetime.strptime(new_date, '%Y-%m-%d')
            data['date'] = new_date
            save_data(data)
            bot.send_message(message.chat.id, f"✅ Дата изменена на *{new_date}*", parse_mode='Markdown')
        except ValueError:
            bot.send_message(message.chat.id, "❌ Неверный формат даты! Используйте ГГГГ-ММ-ДД")
    
    elif command_type == 'place':
        new_place = message.text.strip()
        data['place'] = new_place
        save_data(data)
        bot.send_message(message.chat.id, f"✅ Место изменено на:\n*{new_place}*", parse_mode='Markdown')

# ===== ОСТАЛЬНЫЕ ФУНКЦИИ =====
@bot.message_handler(func=lambda m: m.text == "⏰ Расписание")
def show_schedule(message):
    data = load_data()
    
    schedule_text = (
        f"⏰ *РАСПИСАНИЕ ТРЕНИРОВОК*\n\n"
        f"*Ближайшая тренировка:*\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}\n"
        f"📍 {data['place']}\n\n"
        f"*Регулярное расписание:*\n"
        f"▪️ Вторник Пехорка: 20:45\n"
        f"▪️ Суббота Ляпкина: 09:00\n\n"
        f"*Администратор:* https://t.me/Serega1202"
    )
    bot.send_message(message.chat.id, schedule_text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def show_help(message):
    help_text = (
        "❓ *ПОМОЩЬ*\n\n"
        "*Как пользоваться:*\n"
        "1. 📝 *Записаться* - добавиться в список\n"
        "2. 👥 *Список* - посмотреть участников (с фамилиями)\n"
        "3. ⏰ *Расписание* - узнать время и место\n"
        "4. 🚫 *Отменить* - отменить запись\n"
        "5. 👑 *Админ* - управление тренировкой\n\n"
        "*Система записи:*\n"
        f"• Основной список: {MAX_MAIN} человек\n"
        f"• Резерв: {MAX_RESERVE} человек\n"
        "• При отмене первый из резерва переходит автоматически\n\n"
        "*Администратор:* https://t.me/Serega1202"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# ===== ЗАПУСК БОТА =====
def main():
    logger.info("=" * 60)
    logger.info(f"🏋️‍♂️ SPORTORLOVS BOT ЗАПУЩЕН НА RAILWAY")
    logger.info(f"🤖 Бот: @sportOrlovS_training_bot")
    logger.info(f"👑 Админ: https://t.me/Serega1202")
    logger.info(f"📋 Режим: {MODE_TEXT} ({MAX_MAIN}+{MAX_RESERVE})")
    logger.info("=" * 60)
    
    # Загружаем начальные данные
    load_data()
    
    # Бесконечный цикл с перезапуском при ошибках
    while True:
        try:
            logger.info("Запуск бота...")
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.error(f"Ошибка бота: {e}")
            logger.info("Перезапуск через 10 секунд...")
            time.sleep(10)

if __name__ == '__main__':
    main()
