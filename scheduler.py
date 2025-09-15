from datetime import datetime, timedelta
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler


async def send_reminder(bot: telegram.Bot, telegram_id: int, start_time_str: str):
    """
    Sends a reminder message to the user.
    """
    message = f"🔔 Напоминание: у вас запись в ArtChaos сегодня в {start_time_str}!"
    await bot.send_message(chat_id=telegram_id, text=message)


def schedule_reminders(scheduler: AsyncIOScheduler, bot: telegram.Bot, booking, telegram_id: int):
    """
    Schedules reminders for a booking based on the business logic.
    """
    now = datetime.now()
    time_until_booking = booking.start_time - now
    start_time_str = booking.start_time.strftime('%H:%M')

    if time_until_booking > timedelta(hours=24):
        # Schedule 24-hour reminder
        reminder_time_24h = booking.start_time - timedelta(hours=24)
        scheduler.add_job(send_reminder, 'date', run_date=reminder_time_24h, args=[bot, telegram_id, start_time_str])
        
        # Schedule 1-hour reminder
        reminder_time_1h = booking.start_time - timedelta(hours=1)
        scheduler.add_job(send_reminder, 'date', run_date=reminder_time_1h, args=[bot, telegram_id, start_time_str])

    elif timedelta(hours=1) < time_until_booking <= timedelta(hours=24):
        # Schedule only 1-hour reminder
        reminder_time_1h = booking.start_time - timedelta(hours=1)
        scheduler.add_job(send_reminder, 'date', run_date=reminder_time_1h, args=[bot, telegram_id, start_time_str])

    # If less than 1 hour, do nothing as per requirements.
