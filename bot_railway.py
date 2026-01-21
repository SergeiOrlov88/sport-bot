import telebot
from telebot import types
import json
import os
import time
from datetime import datetime, timedelta
import logging
from pytz import timezone

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== КОНФИГУРАЦИЯ =====
TOKEN = os.environ.get('BOT_TOKEN', '7833029282:AAEsIe3pamC2UpN3O8hQkiVVbYNBLCLAjxc')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '340480842'))

# ===== РЕЖИМ РАБОТЫ =====
TEST_MODE = os.environ.get('TEST_MODE', 'False').lower() == 'true'

if TEST_MODE:
    MAX_MAIN = 3
    MAX_RESERVE = 2
    MODE_TEXT = "ТЕСТОВЫЙ РЕЖИМ"
else:
    MAX_MAIN = 20
    MAX_RESERVE = 10
    MODE_TEXT = "РАБОЧИЙ РЕЖИМ"

bot = telebot.TeleBot(TOKEN, skip_pending=True)

# ===== ПРОСТОЙ ПУТЬ К ФАЙЛУ =====
DATA_FILE = "training_data.json"  # Файл в текущей папке

# ===== ТАЙМЗОНА =====
MOSCOW_TZ = timezone('Europe/Moscow')

def get_moscow_time():
    return datetime.now(MOSCOW_TZ)

def format_moscow_time(dt=None):
    if dt is None:
        dt = get_moscow_time()
    return dt.strftime('%H:%M')

def format_moscow_date(dt=None):
    if dt is None:
        dt = get_moscow_time()
    return dt.strftime('%Y-%m-%d')

# ===== ХРАНЕНИЕ ДАННЫХ =====
def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Проверяем обязательные поля
            if 'main' not in data:
                data['main'] = []
            if 'reserve' not in data:
                data['reserve'] = []
            if 'manual_entries' not in data:
                data['manual_entries'] = []
            if 'time' not in data:
                data['time'] = '20:45'
            if 'date' not in data:
                data['date'] = format_moscow_date()
            if 'place' not in data:
                data['place'] = 'Пехорка, вторник'
            if 'registration_open' not in data:
                data['registration_open'] = True
            
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
    
    # Создаем новые данные
    return create_default_data()

def create_default_data():
    data = {
        'main': [],
        'reserve': [],
        'time': '20:45',
        'date': format_moscow_date(),
        'place': 'Пехорка, вторник',
        'registration_open': True,
        'manual_entries': []
    }
    save_data(data)
    return data

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Данные сохранены в {DATA_FILE}")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

def is_admin(user_id):
    return user_id == ADMIN_ID

# ===== КОМАНДА /start =====
@bot.message_handler(commands=['start'])
def start(message):
    data = load_data()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["📝 Записаться", "👥 Список", "⏰ Расписание", "🚫 Отменить", "❓ Помощь"]
    
    if is_admin(message.from_user.id):
        buttons.append("👑 Админ")
    
    markup.add(*[types.KeyboardButton(btn) for btn in buttons])
    
    text = (
        f"🏋️‍♂️ *SportOrlovS Training Bot* ({MODE_TEXT})\n\n"
        f"*Следующая тренировка:*\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}\n"
        f"📍 {data['place']}\n"
        f"👥 *Лимиты:* {MAX_MAIN} осн. + {MAX_RESERVE} рез.\n\n"
        f"Выберите действие:"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

# ===== СПИСОК УЧАСТНИКОВ (БЕЗОПАСНЫЙ) =====
@bot.message_handler(func=lambda m: m.text == "👥 Список")
def show_list(message):
    try:
        data = load_data()
        all_main = data['main'] + data.get('manual_entries', [])
        
        # БЕЗ Markdown - безопасно
        text = f"🏋️‍♂️ ТРЕНИРОВКА {data['date']}\n"
        text += f"⏰ Время: {data['time']}\n"
        text += f"📍 Место: {data['place']}\n"
        text += f"👥 Лимиты: {MAX_MAIN}+{MAX_RESERVE}\n\n"
        
        text += f"✅ Основной список ({len(all_main)}/{MAX_MAIN}):\n"
        if all_main:
            for i, user in enumerate(all_main, 1):
                name = user.get('display_name', 'Неизвестно')
                # Убираем спецсимволы
                name = name.replace('*', '').replace('_', '').replace('`', '')
                mark = " 👑" if user.get('is_manual') else ""
                text += f"{i}. {name}{mark}\n"
        else:
            text += "Пока никого\n"
        
        text += f"\n⏳ Резерв ({len(data['reserve'])}/{MAX_RESERVE}):\n"
        if data['reserve']:
            for i, user in enumerate(data['reserve'], 1):
                name = user.get('display_name', 'Неизвестно')
                name = name.replace('*', '').replace('_', '').replace('`', '')
                text += f"{i}. {name}\n"
        else:
            text += "Пока никого\n"
        
        text += f"\n📊 Всего записано: {len(all_main) + len(data['reserve'])}"
        
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {str(e)[:100]}")
        logger.error(f"Ошибка в show_list: {e}")

# ===== ЗАПИСЬ НА ТРЕНИРОВКУ =====
@bot.message_handler(func=lambda m: m.text == "📝 Записаться")
def sign_up(message):
    data = load_data()
    
    if not data['registration_open']:
        bot.send_message(message.chat.id, "❌ Запись закрыта!")
        return
    
    user_id = message.from_user.id
    
    # Проверка дубликатов
    all_users = data['main'] + data['reserve'] + data.get('manual_entries', [])
    for user in all_users:
        if user.get('id') == user_id:
            bot.send_message(message.chat.id, "❌ Вы уже записаны!")
            return
    
    msg = bot.send_message(
        message.chat.id,
        "✏️ Введите имя для отображения в списке:"
    )
    bot.register_next_step_handler(msg, lambda m: process_name(m, user_id))

def process_name(message, user_id):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ Имя не может быть пустым!")
        return
    
    data = load_data()
    
    # Проверяем дубликат имени
    for user in data['main'] + data['reserve']:
        if user.get('display_name', '').lower() == name.lower():
            bot.send_message(message.chat.id, "❌ Это имя уже занято!")
            return
    
    user_data = {
        'id': user_id,
        'display_name': name,
        'username': message.from_user.username or '',
        'time': format_moscow_time(),
        'is_manual': False
    }
    
    all_main_count = len(data['main']) + len(data.get('manual_entries', []))
    
    if all_main_count < MAX_MAIN:
        data['main'].append(user_data)
        status = f"✅ {name}, вы в основном списке!"
    elif len(data['reserve']) < MAX_RESERVE:
        data['reserve'].append(user_data)
        status = f"⏳ {name}, вы в резерве!"
    else:
        bot.send_message(message.chat.id, "❌ Все места заняты!")
        return
    
    save_data(data)
    bot.send_message(message.chat.id, status)
    show_list(message)

# ===== ОТМЕНА ЗАПИСИ =====
@bot.message_handler(func=lambda m: m.text == "🚫 Отменить")
def cancel_registration(message):
    data = load_data()
    user_id = message.from_user.id
    
    # Ищем в основном списке
    for i, user in enumerate(data['main']):
        if user.get('id') == user_id:
            removed = data['main'].pop(i)
            name = removed.get('display_name', 'Неизвестно')
            
            # Переводим из резерва
            if data['reserve']:
                promoted = data['reserve'].pop(0)
                data['main'].append(promoted)
                promoted_name = promoted.get('display_name', 'Неизвестно')
                
                try:
                    if promoted.get('id'):
                        bot.send_message(
                            promoted['id'],
                            f"🎉 {promoted_name}, вы переведены в основной список!"
                        )
                except:
                    pass
                
                save_data(data)
                bot.send_message(
                    message.chat.id,
                    f"✅ {name}, запись отменена!\n🔄 {promoted_name} переведен из резерва."
                )
            else:
                save_data(data)
                bot.send_message(message.chat.id, f"✅ {name}, запись отменена!")
            return
    
    # Ищем в резерве
    for i, user in enumerate(data['reserve']):
        if user.get('id') == user_id:
            removed = data['reserve'].pop(i)
            name = removed.get('display_name', 'Неизвестно')
            save_data(data)
            bot.send_message(message.chat.id, f"✅ {name}, запись отменена!")
            return
    
    bot.send_message(message.chat.id, "❌ Вы не записаны")

# ===== РАСПИСАНИЕ =====
@bot.message_handler(func=lambda m: m.text == "⏰ Расписание")
def show_schedule(message):
    data = load_data()
    text = (
        f"⏰ РАСПИСАНИЕ\n\n"
        f"Ближайшая тренировка:\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}\n"
        f"📍 {data['place']}\n\n"
        f"Регулярное:\n"
        f"▪️ Вторник: 20:45 (Пехорка)\n"
        f"▪️ Суббота: 09:00 (Ляпкина)\n\n"
        f"Текущее время: {format_moscow_time()}"
    )
    bot.send_message(message.chat.id, text)

# ===== ПОМОЩЬ =====
@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def show_help(message):
    text = (
        "❓ ПОМОЩЬ\n\n"
        "Как пользоваться:\n"
        "1. 📝 Записаться - добавиться в список\n"
        "2. 👥 Список - посмотреть участников\n"
        "3. ⏰ Расписание - время и место\n"
        "4. 🚫 Отменить - отменить свою запись\n\n"
        f"Лимиты: {MAX_MAIN} осн. + {MAX_RESERVE} рез.\n"
        "При отмене первый из резерва переходит автоматически"
    )
    bot.send_message(message.chat.id, text)

# ===== АДМИН =====
@bot.message_handler(func=lambda m: m.text == "👑 Админ" and is_admin(m.from_user.id))
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("⏰ Время", "admin_time"),
        ("📅 Дата", "admin_date"),
        ("📍 Место", "admin_place"),
        ("🔄 Новая", "admin_new"),
        ("🔓 Открыть", "admin_open"),
        ("🔒 Закрыть", "admin_close"),
        ("👤 Добавить", "admin_add"),
        ("🗑️ Удалить", "admin_remove"),
        ("📊 Статистика", "admin_stats")
    ]
    
    for text, callback in buttons:
        markup.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    data = load_data()
    all_main = len(data['main']) + len(data.get('manual_entries', []))
    
    text = (
        f"👑 АДМИН-ПАНЕЛЬ\n\n"
        f"Тренировка:\n"
        f"📅 {data['date']}\n"
        f"⏰ {data['time']}\n"
        f"📍 {data['place']}\n"
        f"👥 {all_main}/{MAX_MAIN} + {len(data['reserve'])}/{MAX_RESERVE}\n"
        f"📝 Запись: {'открыта ✅' if data['registration_open'] else 'закрыта ❌'}"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

# ===== CALLBACK ОБРАБОТЧИК =====
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data.startswith('admin_') and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Нет доступа!")
        return
    
    try:
        if call.data == 'admin_time':
            msg = bot.send_message(call.message.chat.id, "Введите время (например 20:45):")
            bot.register_next_step_handler(msg, lambda m: admin_set_time(m, call.message.chat.id))
        
        elif call.data == 'admin_date':
            msg = bot.send_message(call.message.chat.id, "Введите дату (ГГГГ-ММ-ДД):")
            bot.register_next_step_handler(msg, lambda m: admin_set_date(m, call.message.chat.id))
        
        elif call.data == 'admin_place':
            msg = bot.send_message(call.message.chat.id, "Введите место:")
            bot.register_next_step_handler(msg, lambda m: admin_set_place(m, call.message.chat.id))
        
        elif call.data == 'admin_new':
            data = create_default_data()
            bot.send_message(call.message.chat.id, "🔄 Создана новая тренировка!")
        
        elif call.data == 'admin_open':
            data = load_data()
            data['registration_open'] = True
            save_data(data)
            bot.send_message(call.message.chat.id, "🔓 Запись открыта!")
        
        elif call.data == 'admin_close':
            data = load_data()
            data['registration_open'] = False
            save_data(data)
            bot.send_message(call.message.chat.id, "🔒 Запись закрыта!")
        
        elif call.data == 'admin_stats':
            data = load_data()
            all_main = len(data['main']) + len(data.get('manual_entries', []))
            text = (
                f"📊 СТАТИСТИКА\n\n"
                f"Основной: {all_main}/{MAX_MAIN}\n"
                f"Резерв: {len(data['reserve'])}/{MAX_RESERVE}\n"
                f"Всего: {all_main + len(data['reserve'])}\n\n"
                f"Файл: {DATA_FILE}\n"
                f"Размер: {os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0} байт"
            )
            bot.send_message(call.message.chat.id, text)
        
        elif call.data == 'admin_add':
            msg = bot.send_message(call.message.chat.id, "Введите имя участника:")
            bot.register_next_step_handler(msg, admin_add_user)
        
        elif call.data == 'admin_remove':
            data = load_data()
            all_users = data['main'] + data.get('manual_entries', []) + data['reserve']
            if not all_users:
                bot.send_message(call.message.chat.id, "❌ Список пуст!")
                return
            
            text = "Выберите номер для удаления:\n"
            for i, user in enumerate(all_users[:20], 1):
                name = user.get('display_name', 'Неизвестно')
                text += f"{i}. {name}\n"
            
            msg = bot.send_message(call.message.chat.id, text)
            bot.register_next_step_handler(msg, lambda m: admin_remove_user(m, all_users))
    
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Ошибка: {str(e)[:100]}")
    
    bot.answer_callback_query(call.id)

def admin_set_time(message, chat_id):
    if not is_admin(message.from_user.id):
        return
    data = load_data()
    data['time'] = message.text.strip()
    save_data(data)
    bot.send_message(chat_id, f"✅ Время изменено на {data['time']}")

def admin_set_date(message, chat_id):
    if not is_admin(message.from_user.id):
        return
    try:
        datetime.strptime(message.text.strip(), '%Y-%m-%d')
        data = load_data()
        data['date'] = message.text.strip()
        save_data(data)
        bot.send_message(chat_id, f"✅ Дата изменена на {data['date']}")
    except:
        bot.send_message(chat_id, "❌ Неверный формат даты!")

def admin_set_place(message, chat_id):
    if not is_admin(message.from_user.id):
        return
    data = load_data()
    data['place'] = message.text.strip()
    save_data(data)
    bot.send_message(chat_id, f"✅ Место изменено на {data['place']}")

def admin_add_user(message):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ Имя не может быть пустым!")
        return
    
    data = load_data()
    
    # Проверяем дубликаты
    all_users = data['main'] + data['reserve'] + data.get('manual_entries', [])
    for user in all_users:
        if user.get('display_name', '').lower() == name.lower():
            bot.send_message(message.chat.id, "❌ Это имя уже занято!")
            return
    
    user_data = {
        'display_name': name,
        'time': format_moscow_time(),
        'is_manual': True
    }
    
    all_main_count = len(data['main']) + len(data.get('manual_entries', []))
    
    if all_main_count < MAX_MAIN:
        data.setdefault('manual_entries', []).append(user_data)
        bot.send_message(message.chat.id, f"✅ {name} добавлен в основной список!")
    elif len(data['reserve']) < MAX_RESERVE:
        data['reserve'].append(user_data)
        bot.send_message(message.chat.id, f"⏳ {name} добавлен в резерв!")
    else:
        bot.send_message(message.chat.id, "❌ Все места заняты!")
        return
    
    save_data(data)

def admin_remove_user(message, all_users):
    if not is_admin(message.from_user.id):
        return
    try:
        num = int(message.text.strip())
        if 1 <= num <= len(all_users):
            user = all_users[num-1]
            name = user.get('display_name', 'Неизвестно')
            
            data = load_data()
            
            # Удаляем из нужного списка
            if user in data['main']:
                data['main'].remove(user)
            elif user in data.get('manual_entries', []):
                data['manual_entries'].remove(user)
            elif user in data['reserve']:
                data['reserve'].remove(user)
            
            save_data(data)
            bot.send_message(message.chat.id, f"✅ {name} удален!")
        else:
            bot.send_message(message.chat.id, "❌ Неверный номер!")
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")

# ===== ЗАПУСК =====
def main():
    logger.info(f"🚀 Бот запущен. Режим: {MODE_TEXT}")
    logger.info(f"📁 Файл данных: {DATA_FILE}")
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            time.sleep(10)

if __name__ == '__main__':
    main()
