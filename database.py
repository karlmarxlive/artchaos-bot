"""
Модуль для работы с базой данных SQLite.
Содержит модели данных и функции для управления бронированиями.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Создаем базовый класс для моделей
Base = declarative_base()


class Booking(Base):
    """
    Модель для хранения информации о бронированиях.
    """
    __tablename__ = 'bookings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)  # ID пользователя в Telegram
    username = Column(String(100), nullable=True)  # Имя пользователя (необязательно)
    start_time = Column(DateTime, nullable=False)  # Время начала бронирования
    end_time = Column(DateTime, nullable=False)  # Время окончания бронирования
    
    def __repr__(self):
        return f"<Booking(id={self.id}, user_id={self.user_id}, start_time={self.start_time})>"


# Глобальные переменные для подключения к БД
engine = None
async_session = None


async def init_database():
    """
    Инициализация базы данных и создание таблиц.
    """
    global engine, async_session
    
    # Создаем асинхронный движок для SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///bookings.db",
        echo=False  # Установите True для отладки SQL запросов
    )
    
    # Создаем фабрику сессий
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Создаем все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_database():
    """
    Закрытие соединения с базой данных.
    """
    if engine:
        await engine.dispose()


async def add_booking(user_id: int, username: Optional[str], start_time: datetime, end_time: datetime) -> bool:
    """
    Добавляет новое бронирование в базу данных.
    
    Args:
        user_id: ID пользователя в Telegram
        username: Имя пользователя (может быть None)
        start_time: Время начала бронирования
        end_time: Время окончания бронирования
    
    Returns:
        bool: True если бронирование успешно добавлено, False в случае ошибки
    """
    try:
        async with async_session() as session:
            # Создаем новый объект бронирования
            booking = Booking(
                user_id=user_id,
                username=username,
                start_time=start_time,
                end_time=end_time
            )
            
            # Добавляем в сессию и сохраняем
            session.add(booking)
            await session.commit()
            
            print(f"Бронирование добавлено: {booking}")
            return True
            
    except Exception as e:
        print(f"Ошибка при добавлении бронирования: {e}")
        return False


async def get_user_bookings(user_id: int) -> list:
    """
    Получает все бронирования пользователя.
    
    Args:
        user_id: ID пользователя в Telegram
    
    Returns:
        list: Список бронирований пользователя
    """
    try:
        async with async_session() as session:
            from sqlalchemy import select
            
            # Выполняем запрос
            result = await session.execute(
                select(Booking).where(Booking.user_id == user_id)
            )
            bookings = result.scalars().all()
            
            return list(bookings)
            
    except Exception as e:
        print(f"Ошибка при получении бронирований: {e}")
        return []


async def check_booking_conflict(start_time: datetime, end_time: datetime) -> bool:
    """
    Проверяет, есть ли конфликт с существующими бронированиями.
    
    Args:
        start_time: Время начала нового бронирования
        end_time: Время окончания нового бронирования
    
    Returns:
        bool: True если есть конфликт, False если время свободно
    """
    try:
        async with async_session() as session:
            from sqlalchemy import select, and_, or_
            
            # Ищем пересекающиеся бронирования
            result = await session.execute(
                select(Booking).where(
                    or_(
                        # Новое бронирование начинается во время существующего
                        and_(Booking.start_time <= start_time, Booking.end_time > start_time),
                        # Новое бронирование заканчивается во время существующего
                        and_(Booking.start_time < end_time, Booking.end_time >= end_time),
                        # Новое бронирование полностью содержит существующее
                        and_(Booking.start_time >= start_time, Booking.end_time <= end_time)
                    )
                )
            )
            conflicting_bookings = result.scalars().all()
            
            return len(conflicting_bookings) > 0
            
    except Exception as e:
        print(f"Ошибка при проверке конфликтов: {e}")
        return True  # В случае ошибки считаем, что есть конфликт


# Функция для тестирования (можно удалить в продакшене)
async def test_database():
    """
    Простая функция для тестирования работы с базой данных.
    """
    await init_database()
    
    # Тестовое бронирование
    test_start = datetime.now() + timedelta(days=1)
    test_end = test_start + timedelta(hours=2)
    
    success = await add_booking(12345, "test_user", test_start, test_end)
    print(f"Тестовое бронирование добавлено: {success}")
    
    bookings = await get_user_bookings(12345)
    print(f"Бронирования пользователя: {bookings}")
    
    await close_database()


if __name__ == "__main__":
    # Запуск тестирования
    asyncio.run(test_database())
