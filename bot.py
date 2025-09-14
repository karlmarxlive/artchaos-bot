"""
Telegram-бот для бронирования времени в творческой мастерской.
Использует python-telegram-bot v20+ с асинхронным API.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, time
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ConversationHandler, ContextTypes, MessageHandler, filters
)

from database import (
    init_database, close_database, add_booking, check_booking_conflict,
    get_or_create_user, get_user_abonement, decrease_user_visits, add_user_visits,
    has_booking_on_date
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота из переменной окружения
BOT_TOKEN = os.getenv("TELEGRAM_TEST_BOT_API")

if not BOT_TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_TEST_BOT_API не установлена!")

# Состояния для ConversationHandler
SELECTING_DATE, SELECTING_TIME, SELECTING_DURATION = range(3)

# Доступные временные слоты (можно настроить под ваши нужды)
TIME_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", 
    "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"
]


# ID администратора (замените на свой)
ADMIN_TELEGRAM_ID = 411840215  # Замените на ваш Telegram ID


def get_date_buttons() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопками для выбора даты (ближайшие 7 дней).
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с датами
    """
    keyboard = []
    today = datetime.now().date()
    
    # Создаем кнопки для ближайших 7 дней
    for i in range(7):
        date = today + timedelta(days=i)
        button_text = date.strftime("%d.%m (%a)")
        callback_data = f"date_{date.strftime('%Y-%m-%d')}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    return InlineKeyboardMarkup(keyboard)


def get_time_buttons() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопками для выбора времени.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с временными слотами
    """
    keyboard = []
    
    # Создаем кнопки по 2 в ряд для лучшего отображения
    for i in range(0, len(TIME_SLOTS), 2):
        row = []
        for j in range(2):
            if i + j < len(TIME_SLOTS):
                time_slot = TIME_SLOTS[i + j]
                row.append(InlineKeyboardButton(time_slot, callback_data=f"time_{time_slot}"))
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start.
    """
    user = update.effective_user
    welcome_message = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Добро пожаловать в бот для бронирования времени в творческой мастерской! 🎨\n\n"
        "Доступные команды:\n"
        "/book - Забронировать время\n"
        "/help - Показать справку"
    )
    
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /help.
    """
    user = update.effective_user
    
    help_text = (
        "📋 Справка по использованию бота:\n\n"
        "/start - Начать работу с ботом\n"
        "/book - Забронировать время в мастерской\n"
        "/help - Показать эту справку\n\n"
        "💡 Для бронирования используйте команду /book и следуйте инструкциям бота.\n"
        "🎫 Для бронирования необходимо иметь абонемент с доступными посещениями."
    )
    
    # Добавляем админские команды для администратора
    if user.id == ADMIN_TELEGRAM_ID:
        help_text += (
            "\n\n🔧 Админские команды:\n"
            "/add_visits <telegram_id> <количество> - Добавить посещения пользователю"
        )
    
    await update.message.reply_text(help_text)


async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало диалога бронирования. Показывает доступные даты.
    
    Returns:
        int: Следующее состояние ConversationHandler
    """
    user = update.effective_user
    
    # Получаем или создаем пользователя в базе данных
    db_user = await get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    if db_user is None:
        await update.message.reply_text(
            "❌ Произошла ошибка при работе с базой данных. Попробуйте позже."
        )
        return ConversationHandler.END
    
    # Сохраняем внутренний ID пользователя из БД в контексте
    context.user_data['user_id'] = db_user.id
    context.user_data['telegram_id'] = user.id
    context.user_data['username'] = user.username or user.first_name
    
    message = (
        "📅 На какой день вы хотите записаться?\n\n"
        "Выберите дату из списка ниже:"
    )
    
    keyboard = get_date_buttons()
    await update.message.reply_text(message, reply_markup=keyboard)
    
    return SELECTING_DATE


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка выбора даты пользователем.
    
    Returns:
        int: Следующее состояние ConversationHandler
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем дату из callback_data
    date_str = query.data.split('_')[1]  # "date_2024-01-15" -> "2024-01-15"
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Сохраняем выбранную дату в контексте
    context.user_data['selected_date'] = selected_date
    
    message = (
        f"✅ Отлично! Вы выбрали {selected_date.strftime('%d.%m.%Y')}\n\n"
        "🕐 Теперь выберите время начала бронирования:"
    )
    
    keyboard = get_time_buttons()
    await query.edit_message_text(message, reply_markup=keyboard)
    
    return SELECTING_TIME


async def time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка выбора времени. Сохраняет время и запрашивает длительность.
    
    Returns:
        int: Следующее состояние ConversationHandler
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем время из callback_data
    time_str = query.data.split('_')[1]  # "time_14:00" -> "14:00"
    hour, minute = map(int, time_str.split(':'))
    
    # Сохраняем выбранное время в контексте
    context.user_data['selected_time'] = time_str
    context.user_data['selected_hour'] = hour
    context.user_data['selected_minute'] = minute
    
    message = (
        f"✅ Время выбрано: {time_str}\n\n"
        "⏱️ На сколько часов вы хотите записаться?\n\n"
        "Введите число (например, 1.5 или 2) или минуты (например, 30):"
    )
    
    await query.edit_message_text(message)
    return SELECTING_DURATION


async def duration_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка выбора длительности и создание бронирования.
    
    Returns:
        int: Завершение ConversationHandler
    """
    # Извлекаем текст из сообщения пользователя
    duration_text = update.message.text.strip()
    
    try:
        # Пытаемся преобразовать в число
        duration_value = float(duration_text)
        
        # Умный парсинг: если число больше 8, считаем его минутами
        if duration_value > 8:
            # Считаем как минуты
            duration_hours = duration_value / 60
        else:
            # Считаем как часы
            duration_hours = duration_value
        
        # Проверяем, что число в допустимом диапазоне (от 0.5 до 8 часов)
        if duration_hours < 0.5 or duration_hours > 8:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число часов (например, 1.5 или 2) или минут (например, 30).\n\n"
                "Диапазон: от 30 минут до 8 часов.\n"
                "Попробуйте еще раз:"
            )
            return SELECTING_DURATION
            
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите корректное число часов (например, 1.5 или 2) или минут (например, 30).\n\n"
            "Попробуйте еще раз:"
        )
        return SELECTING_DURATION
    
    # Получаем данные из контекста
    user_id = context.user_data['user_id']
    selected_date = context.user_data['selected_date']
    selected_hour = context.user_data['selected_hour']
    selected_minute = context.user_data['selected_minute']
    selected_time = context.user_data['selected_time']
    
    # Создаем datetime объекты для начала и окончания бронирования
    start_time = datetime.combine(selected_date, time(selected_hour, selected_minute))
    end_time = start_time + timedelta(hours=duration_hours)
    
    # Проверяем, не конфликтует ли бронирование с существующими
    has_conflict = await check_booking_conflict(start_time, end_time)
    
    if has_conflict:
        message = (
            "❌ Увы, выбранное время и длительность уже заняты.\n\n"
            "Пожалуйста, выберите другое время начала:"
        )
        keyboard = get_time_buttons()
        await update.message.reply_text(message, reply_markup=keyboard)
        return SELECTING_TIME
    
    # Проверяем, является ли это первым бронированием пользователя на выбранную дату
    is_first_booking_today = not await has_booking_on_date(user_id, selected_date)
    
    # Если это первое бронирование за день, проверяем и списываем посещение
    if is_first_booking_today:
        # Проверяем абонемент пользователя
        abonement = await get_user_abonement(user_id)
        
        if abonement is None or abonement.visits_left <= 0:
            message = (
                "❌ У вас нет доступных посещений. Пожалуйста, сначала приобретите абонемент с помощью команды /buy."
            )
            await update.message.reply_text(message)
            return ConversationHandler.END
        
        # Списываем одно посещение
        visit_decreased = await decrease_user_visits(user_id)
        
        if not visit_decreased:
            message = (
                "❌ Не удалось списать посещение. Попробуйте еще раз."
            )
            await update.message.reply_text(message)
            return ConversationHandler.END
    
    # Добавляем бронирование в базу данных (в любом случае)
    success = await add_booking(user_id, start_time, end_time)
    
    if success:
        # Форматируем длительность для отображения
        if duration_hours == 1:
            duration_text = "1 час"
        elif duration_hours < 1:
            minutes = int(duration_hours * 60)
            duration_text = f"{minutes} минут"
        elif duration_hours == int(duration_hours):
            duration_text = f"{int(duration_hours)} часа"
        else:
            duration_text = f"{duration_hours} часа"
        
        # Формируем сообщение в зависимости от того, было ли списано посещение
        if is_first_booking_today:
            # Получаем обновленную информацию об абонементе
            updated_abonement = await get_user_abonement(user_id)
            visits_left = updated_abonement.visits_left if updated_abonement else 0
            
            message = (
                f"🎉 Поздравляем! Вы успешно записаны!\n\n"
                f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
                f"🕐 Время: {selected_time} - {end_time.strftime('%H:%M')}\n"
                f"⏱️ Длительность: {duration_text}\n"
                f"🎫 Осталось посещений: {visits_left}\n\n"
                "До встречи в мастерской! 🎨"
            )
        else:
            message = (
                f"🎉 Поздравляем! Вы успешно записаны!\n\n"
                f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
                f"🕐 Время: {selected_time} - {end_time.strftime('%H:%M')}\n"
                f"⏱️ Длительность: {duration_text}\n\n"
                "💡 Это дополнительное бронирование на сегодня - посещение не списано.\n"
                "До встречи в мастерской! 🎨"
            )
    else:
        # Если бронирование не удалось, возвращаем посещение только если оно было списано
        if is_first_booking_today:
            await add_user_visits(user_id, 1)
        
        message = (
            "❌ Произошла ошибка при сохранении бронирования.\n\n"
            "Пожалуйста, попробуйте еще раз, используя команду /book"
        )
    
    await update.message.reply_text(message)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отмена диалога бронирования.
    
    Returns:
        int: Завершение ConversationHandler
    """
    await update.message.reply_text(
        "❌ Бронирование отменено.\n\n"
        "Если захотите забронировать время, используйте команду /book"
    )
    return ConversationHandler.END


async def add_visits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Админская команда для добавления посещений пользователю.
    Формат: /add_visits <telegram_id> <количество>
    """
    user = update.effective_user
    
    # Проверяем, что команду вызывает администратор
    if user.id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Проверяем аргументы команды
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "❌ Неверный формат команды.\n\n"
            "Используйте: /add_visits <telegram_id> <количество>\n"
            "Пример: /add_visits 123456789 5"
        )
        return
    
    try:
        telegram_id = int(context.args[0])
        count = int(context.args[1])
        
        if count <= 0:
            await update.message.reply_text("❌ Количество посещений должно быть положительным числом.")
            return
        
        # Получаем или создаем пользователя
        db_user = await get_or_create_user(telegram_id, None, None)
        
        if db_user is None:
            await update.message.reply_text("❌ Ошибка при работе с базой данных.")
            return
        
        # Добавляем посещения
        success = await add_user_visits(db_user.id, count)
        
        if success:
            # Получаем обновленную информацию об абонементе
            abonement = await get_user_abonement(db_user.id)
            total_visits = abonement.visits_left if abonement else 0
            
            await update.message.reply_text(
                f"✅ Успешно добавлено {count} посещений пользователю {telegram_id}.\n"
                f"🎫 Всего посещений: {total_visits}"
            )
        else:
            await update.message.reply_text("❌ Ошибка при добавлении посещений.")
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат аргументов. Используйте числа.")
    except Exception as e:
        logger.error(f"Ошибка в команде add_visits: {e}")
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик ошибок.
    """
    logger.error(f"Ошибка при обработке обновления: {update}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз."
        )


def main() -> None:
    """
    Основная функция для запуска бота.
    """
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем ConversationHandler для диалога бронирования
    booking_conversation = ConversationHandler(
        entry_points=[CommandHandler("book", book_start)],
        states={
            SELECTING_DATE: [CallbackQueryHandler(date_selected, pattern="^date_")],
            SELECTING_TIME: [CallbackQueryHandler(time_selected, pattern="^time_")],
            SELECTING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, duration_selected)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="booking_conversation",
        persistent=False,
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_visits", add_visits))
    application.add_handler(booking_conversation)
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Инициализируем базу данных
    async def post_init(application):
        await init_database()
        logger.info("База данных инициализирована")
    
    # Запускаем бота
    logger.info("Запуск бота...")
    application.post_init = post_init
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
