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

# ===== КОНФИГУРАЦИЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
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

bot = telebot.TeleBot(TOKEN)
DATA_FILE = "/data/training_data.json"

# ===== ТАЙМЗОНА МОСКВЫ (UTC+3) =====
MOSCOW_TZ = timezone('Europe/Moscow')

def get_moscow_time():
    """Получение текущего времени по Москве (UTC+3)"""
    return datetime.now(MOSCOW_TZ)

def format_moscow_time(dt=None):
    """Форматирование времени по Москве"""
    if dt is None:
        dt = get_moscow_time()
    return dt.strftime('%H:%M')

def format_moscow_datetime(dt=None):
    """Форматирование даты и времени по Москве"""
    if dt is None:
        dt = get_moscow_time()
    return dt.strftime('%Y-%m-%d %H:%M')

# ===== ХРАНЕНИЕ ДАННЫХ =====
def load_data():
    """Загрузка данных из файла"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                required_fields = {
                    'main': [],
                    'reserve': [],
                    'time': '20:45',
                    'date': get_moscow_time().strftime('%Y-%m-%d'),
                    'place': 'Пехорка, вторник',
                    'registration_open': True,
                    'manual_entries': []  # Для записей от админа
                }
                
                for field, default_value in required_fields.items():
                    if field not in data:
                        data[field] = default_value
                
                return data
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
    
    return create_default_data()

def create_default_data():
    """Создание данных по умолчанию"""
    default_data = {
        'main': [],
        'reserve': [],
        'time': '20:45',
        'date': get_moscow_time().strftime('%Y-%m-%d'),
        'place': 'Пехорка, вторник',
        'registration_open': True,
        'manual_entries': []
    }
    save_data(default_data)
    return default_data

def save_data(data):
    """Сохранение данных"""
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

def is_admin(user_id):
    return user_id == ADMIN_ID

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

# ===== ЗАПИСЬ НА ТРЕНИРОВКУ (С ВОЗМОЖНОСТЬЮ ВВОДА ИМЕНИ) =====
@bot.message_handler(func=lambda m: m.text == "📝 Записаться")
def sign_up(message):
    data = load_data()
    
    if not data['registration_open']:
        bot.send_message(message.chat.id, "❌ Запись закрыта!")
        return
    
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    # Проверяем, не записан ли уже
    for user in data["main"] + data["reserve"] + data.get("manual_entries", []):
        if user.get("id") == user_id:
            bot.send_message(message.chat.id, "❌ Вы уже записаны!")
            return
    
    # Спрашиваем имя для отображения
    msg = bot.send_message(
        message.chat.id,
        "✏️ *Введите имя для отображения в списке:*\n\n"
        "Можно ввести:\n"
        "• Только имя\n"
        "• Имя и фамилию\n"
        "• Прозвище\n"
        "• Любое сочетание\n\n"
        "*Пример:* Иван Иванов или Ваня",
        parse_mode='Markdown'
    )
    
    bot.register_next_step_handler(msg, lambda m: process_name_input(m, user_id, username))

def process_name_input(message, user_id, username):
    """Обработка введенного имени"""
    custom_name = message.text.strip()
    
    if not custom_name or len(custom_name) > 50:
        bot.send_message(message.chat.id, "❌ Имя не может быть пустым или слишком длинным!")
        return
    
    data = load_data()
    
    # Проверяем, не занято ли имя (опционально)
    for user in data["main"] + data["reserve"]:
        if user.get("display_name", "").lower() == custom_name.lower():
            bot.send_message(message.chat.id, "❌ Это имя уже занято! Выберите другое.")
            return
    
    user_info = {
        "id": user_id,
        "telegram_name": message.from_user.first_name,
        "display_name": custom_name,
        "username": username,
        "time": format_moscow_time(),  # Время по Москве
        "is_manual": False,
        "registered_by": user_id
    }
    
    if len(data["main"]) < MAX_MAIN:
        data["main"].append(user_info)
        position = len(data["main"])
        status = f"✅ *{custom_name}*, вы в основном списке! (место {position}/{MAX_MAIN})"
        
    elif len(data["reserve"]) < MAX_RESERVE:
        data["reserve"].append(user_info)
        position = len(data["reserve"])
        status = f"⏳ *{custom_name}*, вы в резерве! (место {position}/{MAX_RESERVE})"
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
        f"▪️ Резерв: {len(data['reserve'])}/{MAX_RESERVE}\n\n"
        f"🕒 *Время записи:* {format_moscow_time()} (МСК)"
    )
    
    bot.send_message(message.chat.id, confirmation, parse_mode='Markdown')
    logger.info(f"Пользователь {user_id} записался как '{custom_name}'")

# ===== СПИСОК УЧАСТНИКОВ =====
@bot.message_handler(func=lambda m: m.text == "👥 Список")
def show_list(message):
    data = load_data()
    
    # Объединяем все записи
    all_main = data["main"] + data.get("manual_entries", [])
    
    text = (
        f"🏋️‍♂️ *ТРЕНИРОВКА {data['date']}* ({MODE_TEXT})\n"
        f"⏰ *Время:* {data['time']}\n"
        f"📍 *Место:* {data['place']}\n"
        f"👥 *Лимиты:* {MAX_MAIN}+{MAX_RESERVE}\n\n"
    )
    
    text += f"✅ *Основной список ({len(all_main)}/{MAX_MAIN}):*\n"
    if all_main:
        for i, user in enumerate(all_main, 1):
            display_name = user.get('display_name', 'Неизвестно')
            username = f"(@{user['username']})" if user.get('username') else ""
            time_str = f" - {user.get('time', '')}" if user.get('time') else ""
            manual_mark = " 👑" if user.get('is_manual') else ""
            text += f"{i}. {display_name} {username}{time_str}{manual_mark}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n⏳ *Резерв ({len(data['reserve'])}/{MAX_RESERVE}):*\n"
    if data["reserve"]:
        for i, user in enumerate(data["reserve"], 1):
            display_name = user.get('display_name', 'Неизвестно')
            username = f"(@{user['username']})" if user.get('username') else ""
            time_str = f" - {user.get('time', '')}" if user.get('time') else ""
            text += f"{i}. {display_name} {username}{time_str}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n📊 *Всего записано:* {len(all_main) + len(data['reserve'])}"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ===== ОТМЕНА ЗАПИСИ =====
@bot.message_handler(func=lambda m: m.text == "🚫 Отменить")
def cancel_registration(message):
    data = load_data()
    user_id = message.from_user.id
    
    # Ищем в основном списке (обычные пользователи)
    for i, user in enumerate(data["main"]):
        if user.get("id") == user_id and not user.get("is_manual", False):
            removed_user = data["main"].pop(i)
            removed_name = removed_user.get('display_name', 'Неизвестно')
            
            # Перевод из резерва
            if data["reserve"]:
                first_reserve = data["reserve"].pop(0)
                data["main"].append(first_reserve)
                promoted_name = first_reserve.get('display_name', 'Неизвестно')
                
                try:
                    if first_reserve.get("id"):
                        bot.send_message(
                            first_reserve["id"],
                            f"🎉 *{promoted_name}, вы переведены в основной список!*\n\n"
                            f"📅 Тренировка: {data['date']}\n"
                            f"⏰ Время: {data['time']}\n"
                            f"📍 Место: {data['place']}"
                        )
                except:
                    pass
                
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
    
    # Ищем в ручных записях админа (только если это админ)
    if is_admin(user_id):
        for i, user in enumerate(data.get("manual_entries", [])):
            bot.send_message(message.chat.id, "❌ Нельзя отменить ручную запись через эту кнопку. Используйте админ-панель.")
            return
    
    # Ищем в резерве
    for i, user in enumerate(data["reserve"]):
        if user.get("id") == user_id and not user.get("is_manual", False):
            removed_user = data["reserve"].pop(i)
            removed_name = removed_user.get('display_name', 'Неизвестно')
            save_data(data)
            
            bot.send_message(
                message.chat.id,
                f"✅ *{removed_name}, ваша запись из резерва отменена!*"
            )
            return
    
    bot.send_message(message.chat.id, "❌ Вы не записаны на тренировку")

# ===== АДМИН-ПАНЕЛЬ С РАСШИРЕННЫМИ ФУНКЦИЯМИ =====
@bot.message_handler(func=lambda m: m.text == "👑 Админ" and is_admin(m.from_user.id))
def admin_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn1 = types.InlineKeyboardButton("⏰ Изменить время", callback_data='admin_set_time')
    btn2 = types.InlineKeyboardButton("📅 Изменить дату", callback_data='admin_set_date')
    btn3 = types.InlineKeyboardButton("📍 Изменить место", callback_data='admin_set_place')
    btn4 = types.InlineKeyboardButton("🔄 Новая тренировка", callback_data='admin_new_training')
    btn5 = types.InlineKeyboardButton("🔓 Открыть запись", callback_data='admin_open_reg')
    btn6 = types.InlineKeyboardButton("🔒 Закрыть запись", callback_data='admin_close_reg')
    btn7 = types.InlineKeyboardButton("👤 Добавить участника", callback_data='admin_add_user')
    btn8 = types.InlineKeyboardButton("🗑️ Удалить участника", callback_data='admin_remove_user')
    btn9 = types.InlineKeyboardButton("📊 Подробная статистика", callback_data='admin_stats')
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9)
    
    data = load_data()
    all_main = data["main"] + data.get("manual_entries", [])
    
    admin_text = (
        f"👑 *АДМИН-ПАНЕЛЬ* ({MODE_TEXT})\n\n"
        f"*Текущая тренировка:*\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}\n"
        f"📍 Место: {data['place']}\n"
        f"👥 Участников: {len(all_main)}/{MAX_MAIN}\n"
        f"⏳ Резерв: {len(data['reserve'])}/{MAX_RESERVE}\n"
        f"📝 Запись: {'открыта ✅' if data['registration_open'] else 'закрыта ❌'}\n"
        f"👤 Ручных записей: {len(data.get('manual_entries', []))}"
    )
    
    bot.send_message(
        message.chat.id,
        admin_text,
        reply_markup=markup,
        parse_mode='Markdown'
    )

# ===== ОБРАБОТКА ВСЕХ CALLBACK-КНОПОК =====
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Обработчик всех callback-кнопок"""
    
    # Админские команды
    if call.data.startswith('admin_'):
        admin_callback_handler(call)
        return
    
    # Удаление участника
    elif call.data.startswith('remove_'):
        remove_user_handler(call)
        return
    
    bot.answer_callback_query(call.id, "❌ Неизвестная команда")

def remove_user_handler(call):
    """Обработчик удаления участника"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Нет доступа!")
        return
    
    try:
        idx = int(call.data.split('_')[1])
        data = load_data()
        
        # Объединяем все списки
        all_main = data["main"] + data.get("manual_entries", [])
        all_reserve = data["reserve"]
        all_users = all_main + all_reserve
        
        if 0 <= idx < len(all_users):
            user_to_remove = all_users[idx]
            display_name = user_to_remove.get('display_name', 'Неизвестно')
            
            # Определяем, откуда удаляем
            removed_from = None
            if user_to_remove in data["main"]:
                data["main"].remove(user_to_remove)
                removed_from = "main"
            elif user_to_remove in data.get("manual_entries", []):
                data["manual_entries"].remove(user_to_remove)
                removed_from = "manual"
            elif user_to_remove in data["reserve"]:
                data["reserve"].remove(user_to_remove)
                removed_from = "reserve"
            
            if removed_from:
                save_data(data)
                
                # Если удалили из основного списка, переводим из резерва
                if removed_from in ["main", "manual"] and data["reserve"]:
                    first_reserve = data["reserve"].pop(0)
                    data["main"].append(first_reserve)
                    promoted_name = first_reserve.get('display_name', 'Неизвестно')
                    
                    try:
                        if first_reserve.get("id"):
                            bot.send_message(
                                first_reserve["id"],
                                f"🎉 *{promoted_name}, вы переведены в основной список!*\n\n"
                                f"📅 Тренировка: {data['date']}\n"
                                f"⏰ Время: {data['time']}\n"
                                f"📍 Место: {data['place']}"
                            )
                    except Exception as e:
                        logger.error(f"Не удалось уведомить: {e}")
                    
                    save_data(data)
                    
                    # Обновляем сообщение
                    bot.edit_message_text(
                        f"✅ *{display_name} удален(а)!*\n"
                        f"🔄 *{promoted_name} переведен из резерва.*",
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode='Markdown'
                    )
                else:
                    bot.edit_message_text(
                        f"✅ *{display_name} удален(а) из списка!*",
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode='Markdown'
                    )
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при удалении")
        else:
            bot.answer_callback_query(call.id, "❌ Участник не найден")
    
    except Exception as e:
        logger.error(f"Ошибка в remove_user_handler: {e}")
        bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
    
    bot.answer_callback_query(call.id)

def process_admin_add_user(message):
    """Добавление участника админом"""
    custom_name = message.text.strip()
    
    if not custom_name:
        bot.send_message(message.chat.id, "❌ Имя не может быть пустым!")
        return
    
    data = load_data()
    
    # Проверяем на дубликаты
    all_users = data["main"] + data["reserve"] + data.get("manual_entries", [])
    for user in all_users:
        if user.get("display_name", "").lower() == custom_name.lower():
            bot.send_message(message.chat.id, "❌ Это имя уже занято!")
            return
    
    user_info = {
        "display_name": custom_name,
        "time": format_moscow_time(),
        "is_manual": True,
        "added_by": "admin",
        "added_at": format_moscow_datetime()
    }
    
    all_main = data["main"] + data.get("manual_entries", [])
    
    if len(all_main) < MAX_MAIN:
        data.setdefault("manual_entries", []).append(user_info)
        position = len(all_main) + 1
        status = f"✅ *{custom_name}* добавлен(а) в основной список! (место {position}/{MAX_MAIN})"
    elif len(data["reserve"]) < MAX_RESERVE:
        data["reserve"].append(user_info)
        position = len(data["reserve"])
        status = f"⏳ *{custom_name}* добавлен(а) в резерв! (место {position}/{MAX_RESERVE})"
    else:
        bot.send_message(message.chat.id, "❌ Все места заняты!")
        return
    
    save_data(data)
    
    confirmation = (
        f"{status}\n\n"
        f"📅 Тренировка: {data['date']}\n"
        f"⏰ Время: {data['time']}\n"
        f"📍 Место: {data['place']}\n\n"
        f"🕒 *Добавлено:* {format_moscow_time()} (МСК)"
    )
    
    bot.send_message(message.chat.id, confirmation, parse_mode='Markdown')
    logger.info(f"Админ добавил участника '{custom_name}'")

def process_admin_time(message):
    if not is_admin(message.from_user.id):
        return
    
    new_time = message.text.strip()
    data = load_data()
    data['time'] = new_time
    save_data(data)
    bot.send_message(message.chat.id, f"✅ Время изменено на *{new_time}*", parse_mode='Markdown')

def process_admin_date(message):
    if not is_admin(message.from_user.id):
        return
    
    new_date = message.text.strip()
    try:
        datetime.strptime(new_date, '%Y-%m-%d')
        data = load_data()
        data['date'] = new_date
        save_data(data)
        bot.send_message(message.chat.id, f"✅ Дата изменена на *{new_date}*", parse_mode='Markdown')
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат даты! Используйте ГГГГ-ММ-ДД")

def process_admin_place(message):
    if not is_admin(message.from_user.id):
        return
    
    new_place = message.text.strip()
    data = load_data()
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
        f"*Текущее время:* {format_moscow_time()} (МСК)\n\n"
        f"*Администратор:* https://t.me/Serega1202"
    )
    bot.send_message(message.chat.id, schedule_text, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def show_help(message):
    help_text = (
        "❓ *ПОМОЩЬ*\n\n"
        "*Как пользоваться:*\n"
        "1. 📝 *Записаться* - добавиться в список (можно ввести любое имя)\n"
        "2. 👥 *Список* - посмотреть всех участников\n"
        "3. ⏰ *Расписание* - узнать время и место\n"
        "4. 🚫 *Отменить* - отменить свою запись\n"
        "5. 👑 *Админ* - управление тренировкой\n\n"
        "*Особенности:*\n"
        f"• Основной список: {MAX_MAIN} человек\n"
        f"• Резерв: {MAX_RESERVE} человек\n"
        "• При отмене первый из резерва переходит автоматически\n"
        "• Время отображается по Москве (МСК)\n"
        "• Можно использовать любое имя при записи\n\n"
        "*Администратор:* https://t.me/Serega1202"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# ===== ЗАПУСК БОТА =====
def main():
    logger.info("=" * 60)
    logger.info(f"🏋️‍♂️ SPORTORLOVS BOT (ОБНОВЛЕННЫЙ)")
    logger.info(f"🤖 Бот: @sportOrlovS_training_bot")
    logger.info(f"👑 Админ: https://t.me/Serega1202")
    logger.info(f"📋 Режим: {MODE_TEXT} ({MAX_MAIN}+{MAX_RESERVE})")
    logger.info(f"🕒 Таймзона: Москва (UTC+3)")
    logger.info("=" * 60)
    
    load_data()
    
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

