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
    ConversationHandler, ContextTypes
)

from database import init_database, close_database, add_booking, check_booking_conflict

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
SELECTING_DATE, SELECTING_TIME = range(2)

# Доступные временные слоты (можно настроить под ваши нужды)
TIME_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", 
    "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"
]

# Длительность бронирования (в часах)
BOOKING_DURATION = 2


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
    help_text = (
        "📋 Справка по использованию бота:\n\n"
        "/start - Начать работу с ботом\n"
        "/book - Забронировать время в мастерской\n"
        "/help - Показать эту справку\n\n"
        "💡 Для бронирования используйте команду /book и следуйте инструкциям бота."
    )
    
    await update.message.reply_text(help_text)


async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало диалога бронирования. Показывает доступные даты.
    
    Returns:
        int: Следующее состояние ConversationHandler
    """
    user = update.effective_user
    
    # Сохраняем информацию о пользователе в контексте
    context.user_data['user_id'] = user.id
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
    Обработка выбора времени и создание бронирования.
    
    Returns:
        int: Завершение ConversationHandler
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем время из callback_data
    time_str = query.data.split('_')[1]  # "time_14:00" -> "14:00"
    hour, minute = map(int, time_str.split(':'))
    
    # Получаем данные из контекста
    user_id = context.user_data['user_id']
    username = context.user_data['username']
    selected_date = context.user_data['selected_date']
    
    # Создаем datetime объекты для начала и окончания бронирования
    start_time = datetime.combine(selected_date, time(hour, minute))
    end_time = start_time + timedelta(hours=BOOKING_DURATION)
    
    # Проверяем, не конфликтует ли бронирование с существующими
    has_conflict = await check_booking_conflict(start_time, end_time)
    
    if has_conflict:
        message = (
            "❌ К сожалению, это время уже занято.\n\n"
            "Пожалуйста, выберите другое время, используя команду /book"
        )
        await query.edit_message_text(message)
        return ConversationHandler.END
    
    # Добавляем бронирование в базу данных
    success = await add_booking(user_id, username, start_time, end_time)
    
    if success:
        message = (
            f"🎉 Поздравляем! Вы успешно записаны!\n\n"
            f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
            f"🕐 Время: {time_str} - {(start_time + timedelta(hours=BOOKING_DURATION)).strftime('%H:%M')}\n"
            f"⏱️ Длительность: {BOOKING_DURATION} часа\n\n"
            "До встречи в мастерской! 🎨"
        )
    else:
        message = (
            "❌ Произошла ошибка при сохранении бронирования.\n\n"
            "Пожалуйста, попробуйте еще раз, используя команду /book"
        )
    
    await query.edit_message_text(message)
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
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="booking_conversation",
        persistent=False,
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
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
