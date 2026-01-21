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

# Используем skip_pending=True чтобы избежать конфликта 409
bot = telebot.TeleBot(TOKEN, skip_pending=True)

# ===== ФИКС: ПРАВИЛЬНЫЙ ПУТЬ ДЛЯ RAILWAY =====
def get_data_file_path():
    """Определяем правильный путь для сохранения данных в Railway"""
    # Пробуем разные варианты путей в порядке приоритета
    possible_paths = [
        os.path.join(os.getcwd(), 'training_data.json'),  # Лучший вариант для Railway
        'training_data.json',  # Текущая папка
        '/tmp/training_data.json',  # Временная папка (если ничего не работает)
    ]
    
    # Проверяем существующие файлы
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"✅ Используем существующий файл: {path}")
            return path
    
    # Если файл не найден, создаем в первом доступном месте
    for path in possible_paths:
        try:
            # Создаем директорию если нужно
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # Создаем файл с тестовыми данными
            default_data = {
                'main': [],
                'reserve': [],
                'time': '20:45',
                'date': get_moscow_time().strftime('%Y-%m-%d'),
                'place': 'Пехорка, вторник',
                'registration_open': True,
                'manual_entries': []
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📁 Создан новый файл данных: {path}")
            return path
        except Exception as e:
            logger.warning(f"Не удалось создать файл по пути {path}: {e}")
            continue
    
    # Если ничего не сработало, используем текущую директорию
    return 'training_data.json'

# Инициализируем путь к файлу данных
DATA_FILE = get_data_file_path()
logger.info(f"📊 Файл данных будет сохранен в: {DATA_FILE}")

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

# ===== ХРАНЕНИЕ ДАННЫХ (ИСПРАВЛЕННОЕ) =====
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
                    'manual_entries': []
                }
                
                for field, default_value in required_fields.items():
                    if field not in data:
                        data[field] = default_value
                
                logger.info(f"📥 Данные загружены. Участников: {len(data['main'])} осн, {len(data.get('manual_entries', []))} ручн, {len(data['reserve'])} резерв")
                return data
        else:
            logger.warning(f"Файл {DATA_FILE} не существует, создаю новый")
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
    logger.info("🆕 Созданы данные по умолчанию")
    return default_data

def save_data(data):
    """Сохранение данных с улучшенным логированием"""
    try:
        # Создаем директорию если нужно
        directory = os.path.dirname(DATA_FILE)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"📁 Создана директория: {directory}")
        
        # Сохраняем данные
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Логируем успешное сохранение
        all_main = len(data['main']) + len(data.get('manual_entries', []))
        logger.info(f"💾 Данные сохранены в {DATA_FILE}. Участников: {all_main} осн, {len(data['reserve'])} резерв")
        
        # Дополнительная проверка для отладки
        if os.path.exists(DATA_FILE):
            file_size = os.path.getsize(DATA_FILE)
            logger.debug(f"Размер файла: {file_size} байт")
        else:
            logger.error(f"❌ Файл не был создан после save_data()!")
            
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных: {e}")
        # Пробуем сохранить в альтернативное место
        try:
            backup_file = 'training_data_backup.json'
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"📦 Создана резервная копия в {backup_file}")
        except:
            logger.error("Не удалось создать резервную копию!")

def is_admin(user_id):
    return user_id == ADMIN_ID

# ===== НОВАЯ КОМАНДА: ПРОВЕРКА СОХРАНЕНИЯ =====
@bot.message_handler(commands=['check_save'])
def check_save_system(message):
    """Проверка системы сохранения данных"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Только для админа!")
        return
    
    import os
    
    text = "🔍 *ПРОВЕРКА СОХРАНЕНИЯ ДАННЫХ*\n\n"
    
    # 1. Информация о файле
    text += f"📁 *Файл данных:* `{DATA_FILE}`\n"
    text += f"📂 *Существует:* {'✅ ДА' if os.path.exists(DATA_FILE) else '❌ НЕТ'}\n"
    
    if os.path.exists(DATA_FILE):
        size = os.path.getsize(DATA_FILE)
        mtime = time.ctime(os.path.getmtime(DATA_FILE))
        text += f"📏 *Размер:* {size} байт\n"
        text += f"🕒 *Изменен:* {mtime}\n"
    
    # 2. Загружаем и показываем данные
    try:
        data = load_data()
        all_main = data['main'] + data.get('manual_entries', [])
        
        text += f"\n📊 *ДАННЫЕ ТРЕНИРОВКИ:*\n"
        text += f"• Дата: {data.get('date', 'Нет')}\n"
        text += f"• Время: {data.get('time', 'Нет')}\n"
        text += f"• Место: {data.get('place', 'Нет')}\n"
        text += f"• Запись: {'открыта ✅' if data.get('registration_open') else 'закрыта ❌'}\n"
        text += f"• Основной список: {len(all_main)}/{MAX_MAIN}\n"
        text += f"• Резерв: {len(data.get('reserve', []))}/{MAX_RESERVE}\n"
        text += f"• Всего: {len(all_main) + len(data.get('reserve', []))}\n"
        
        # 3. Показываем участников
        if all_main:
            text += f"\n👥 *Участники основного списка:*\n"
            for i, user in enumerate(all_main[:10], 1):
                name = user.get('display_name', 'Без имени')
                is_manual = " (ручная)" if user.get('is_manual') else ""
                time_str = f" - {user.get('time', '')}" if user.get('time') else ""
                text += f"{i}. {name}{time_str}{is_manual}\n"
            if len(all_main) > 10:
                text += f"... и еще {len(all_main) - 10} участников\n"
        
        if data.get('reserve'):
            text += f"\n⏳ *Резервный список:*\n"
            for i, user in enumerate(data['reserve'][:5], 1):
                name = user.get('display_name', 'Без имени')
                time_str = f" - {user.get('time', '')}" if user.get('time') else ""
                text += f"{i}. {name}{time_str}\n"
            if len(data['reserve']) > 5:
                text += f"... и еще {len(data['reserve']) - 5} участников\n"
                
        # 4. Информация для отладки
        text += f"\n🔧 *Информация:*\n"
        text += f"• Текущая папка: {os.getcwd()}\n"
        text += f"• Файл найден: {os.path.exists(DATA_FILE)}\n"
        text += f"• Режим: {MODE_TEXT}\n"
        
    except Exception as e:
        text += f"\n❌ Ошибка загрузки данных: {str(e)}"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

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

# ===== ЗАПИСЬ НА ТРЕНИРОВКУ =====
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
        "time": format_moscow_time(),
        "is_manual": False,
        "registered_by": user_id
    }
    
    all_main_count = len(data["main"]) + len(data.get("manual_entries", []))
    
    if all_main_count < MAX_MAIN:
        data["main"].append(user_info)
        position = all_main_count + 1
        status = f"✅ *{custom_name}*, вы в основном списке! (место {position}/{MAX_MAIN})"
        
    elif len(data["reserve"]) < MAX_RESERVE:
        data["reserve"].append(user_info)
        position = len(data["reserve"])
        status = f"⏳ *{custom_name}*, вы в резерве! (место {position}/{MAX_RESERVE})"
    else:
        bot.send_message(message.chat.id, "❌ Все места заняты!")
        return
    
    # ВАЖНО: Сохраняем данные!
    save_data(data)
    logger.info(f"📝 Пользователь {user_id} записался как '{custom_name}'")
    
    # Отправляем подтверждение
    confirmation = (
        f"{status}\n\n"
        f"📅 *Тренировка:*\n"
        f"▪️ Дата: {data['date']}\n"
        f"▪️ Время: {data['time']}\n"
        f"▪️ Место: {data['place']}\n\n"
        f"📊 *Статистика:*\n"
        f"▪️ Основной список: {all_main_count + 1}/{MAX_MAIN}\n"
        f"▪️ Резерв: {len(data['reserve'])}/{MAX_RESERVE}\n\n"
        f"🕒 *Время записи:* {format_moscow_time()} (МСК)\n\n"
        f"💾 *Данные сохранены!*"
    )
    
    bot.send_message(message.chat.id, confirmation, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "👥 Список")
def show_list(message):
    data = load_data()
    
    # Объединяем все записи
    all_main = data["main"] + data.get("manual_entries", [])
    
    # Функция для экранирования текста для Markdown
    def escape_markdown(text):
        if not text:
            return ""
        # Экранируем все спецсимволы Markdown
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    text = (
        f"🏋️‍♂️ *ТРЕНИРОВКА {data['date']}* ({MODE_TEXT})\n"
        f"⏰ *Время:* {data['time']}\n"
        f"📍 *Место:* {data['place']}\n"
        f"👥 *Лимиты:* {MAX_MAIN}+{MAX_RESERVE}\n\n"
    )
    
    text += f"✅ *Основной список ({len(all_main)}/{MAX_MAIN}):*\n"
    if all_main:
        for i, user in enumerate(all_main, 1):
            display_name = escape_markdown(user.get('display_name', 'Неизвестно'))
            username = f"(@{user['username']})" if user.get('username') else ""
            time_str = f" - {user.get('time', '')}" if user.get('time') else ""
            manual_mark = " 👑" if user.get('is_manual') else ""
            text += f"{i}. {display_name} {username}{time_str}{manual_mark}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n⏳ *Резерв ({len(data['reserve'])}/{MAX_RESERVE}):*\n"
    if data["reserve"]:
        for i, user in enumerate(data["reserve"], 1):
            display_name = escape_markdown(user.get('display_name', 'Неизвестно'))
            username = f"(@{user['username']})" if user.get('username') else ""
            time_str = f" - {user.get('time', '')}" if user.get('time') else ""
            text += f"{i}. {display_name} {username}{time_str}\n"
    else:
        text += "Пока никого\n"
    
    text += f"\n📊 *Всего записано:* {len(all_main) + len(data['reserve'])}"
    
    # Отправляем с Markdown
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
    btn7 = types.InlineKeyboardButton("👤 Добавить участника", callback_data='admin_add_user')
    btn8 = types.InlineKeyboardButton("🗑️ Удалить участника", callback_data='admin_remove_user')
    btn9 = types.InlineKeyboardButton("📊 Подробная статистика", callback_data='admin_stats')
    btn10 = types.InlineKeyboardButton("💾 Проверить сохранение", callback_data='admin_check_save')
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9, btn10)
    
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
        f"👤 Ручных записей: {len(data.get('manual_entries', []))}\n\n"
        f"💾 Файл данных: {DATA_FILE}"
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
    logger.info(f"Callback получен: {call.data} от пользователя {call.from_user.id}")
    
    # Проверка прав админа для всех админ-команд
    if call.data.startswith('admin_') and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Нет доступа!")
        return
    
    try:
        if call.data == 'admin_set_time':
            msg = bot.send_message(call.message.chat.id, "⏰ Введите новое время (например: 20:45):")
            bot.register_next_step_handler(msg, process_admin_time)
        
        elif call.data == 'admin_set_date':
            msg = bot.send_message(call.message.chat.id, "📅 Введите новую дату (формат: ГГГГ-ММ-ДД):")
            bot.register_next_step_handler(msg, process_admin_date)
        
        elif call.data == 'admin_set_place':
            msg = bot.send_message(call.message.chat.id, "📍 Введите новое место тренировки:")
            bot.register_next_step_handler(msg, process_admin_place)
        
        elif call.data == 'admin_new_training':
            new_data = create_default_data()
            bot.send_message(call.message.chat.id, "🔄 Создана новая тренировка! Все записи очищены.", parse_mode='Markdown')
        
        elif call.data == 'admin_open_reg':
            data = load_data()
            data['registration_open'] = True
            save_data(data)
            bot.send_message(call.message.chat.id, "🔓 Запись открыта для всех!", parse_mode='Markdown')
        
        elif call.data == 'admin_close_reg':
            data = load_data()
            data['registration_open'] = False
            save_data(data)
            bot.send_message(call.message.chat.id, "🔒 Запись закрыта!", parse_mode='Markdown')
        
        elif call.data == 'admin_add_user':
            msg = bot.send_message(
                call.message.chat.id,
                "👤 *Добавление участника*\n\n"
                "Введите имя для отображения в списке:",
                parse_mode='Markdown'
            )
            bot.register_next_step_handler(msg, process_admin_add_user)
        
        elif call.data == 'admin_remove_user':
            data = load_data()
            all_main = data["main"] + data.get("manual_entries", [])
            all_reserve = data["reserve"]
            all_users = all_main + all_reserve
            
            if not all_users:
                bot.send_message(call.message.chat.id, "❌ Список участников пуст!")
                return
            
            # СОЗДАЕМ ТЕКСТОВЫЙ СПИСОК (упрощенный вариант)
            text = "🗑️ *Выберите номер участника для удаления:*\n\n"
            for i, user in enumerate(all_users[:30]):  # Ограничиваем 30
                display_name = user.get('display_name', 'Неизвестно')
                if user.get('is_manual'):
                    display_name += " 👑"
                text += f"{i+1}. {display_name}\n"
            
            text += "\nОтправьте номер участника для удаления:"
            
            # Отправляем текстовый список
            msg = bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
            
            # Ждем ввода номера
            bot.register_next_step_handler(msg, lambda m: process_remove_by_number(m, all_users))
        
        elif call.data == 'admin_stats':
            data = load_data()
            all_main = data["main"] + data.get("manual_entries", [])
            stats_text = (
                f"📊 *ПОДРОБНАЯ СТАТИСТИКА*\n\n"
                f"*Общая информация:*\n"
                f"▪️ Основной список: {len(all_main)}/{MAX_MAIN}\n"
                f"▪️ Резерв: {len(data['reserve'])}/{MAX_RESERVE}\n"
                f"▪️ Всего записано: {len(all_main) + len(data['reserve'])}\n"
                f"▪️ Ручных записей: {len(data.get('manual_entries', []))}\n\n"
                f"*Время по Москве:*\n"
                f"▪️ Текущее: {format_moscow_time()}\n"
                f"▪️ Дата тренировки: {data['date']}\n"
                f"▪️ Время тренировки: {data['time']}\n\n"
                f"*Система:*\n"
                f"▪️ Запись: {'открыта ✅' if data['registration_open'] else 'закрыта ❌'}\n"
                f"▪️ Режим: {MODE_TEXT}\n"
                f"▪️ Файл данных: {DATA_FILE}\n"
                f"▪️ Размер файла: {os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0} байт"
            )
            bot.send_message(call.message.chat.id, stats_text, parse_mode='Markdown')
        
        elif call.data == 'admin_check_save':
            check_save_system(call.message)
        
        else:
            bot.answer_callback_query(call.id, "❌ Неизвестная команда")
            return
    
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
    
    bot.answer_callback_query(call.id)

def process_remove_by_number(message, all_users):
    """Удаление участника по номеру"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        num = int(message.text.strip())
        if 1 <= num <= len(all_users):
            idx = num - 1
            user_to_remove = all_users[idx]
            display_name = user_to_remove.get('display_name', 'Неизвестно')
            
            data = load_data()
            
            # Удаляем из соответствующего списка
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
                
                # Перевод из резерва при необходимости
                if removed_from in ["main", "manual"] and data["reserve"]:
                    first_reserve = data["reserve"].pop(0)
                    data["main"].append(first_reserve)
                    promoted_name = first_reserve.get('display_name', 'Неизвестно')
                    
                    try:
                        if first_reserve.get("id"):
                            bot.send_message(
                                first_reserve["id"],
                                f"🎉 *{promoted_name}, вы переведены в основной список!*"
                            )
                    except:
                        pass
                    
                    save_data(data)
                    bot.send_message(
                        message.chat.id,
                        f"✅ *{display_name} удален(а)!*\n"
                        f"🔄 *{promoted_name} переведен из резерва.*",
                        parse_mode='Markdown'
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        f"✅ *{display_name} удален(а) из списка!*",
                        parse_mode='Markdown'
                    )
            else:
                bot.send_message(message.chat.id, "❌ Ошибка при удалении")
        else:
            bot.send_message(message.chat.id, "❌ Неверный номер!")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число!")
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)[:100]}")

def process_admin_add_user(message):
    """Добавление участника админом"""
    if not is_admin(message.from_user.id):
        return
    
    custom_name = message.text.strip()
    
    if not custom_name:
        bot.send_message(message.chat.id, "❌ Имя не может быть пустым!")
        return
    
    data = load_data()
    
    # Проверяем на дубликаты
    all_users = data["main"] + data["reserve"]

