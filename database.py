"""
Модуль для работы с базой данных SQLite.
Содержит модели данных и функции для управления бронированиями.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm import sessionmaker

# Создаем базовый класс для моделей
Base = declarative_base()


class User(Base):
    """
    Модель для хранения информации о пользователях.
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)  # ID пользователя в Telegram
    username = Column(String(100), nullable=True)  # Имя пользователя в Telegram
    first_name = Column(String(100), nullable=True)  # Имя пользователя
    
    # Связи
    abonement = relationship("Abonement", back_populates="user", uselist=False)
    bookings = relationship("Booking", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Abonement(Base):
    """
    Модель для хранения информации об абонементах пользователей.
    """
    __tablename__ = 'abonements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    visits_left = Column(Integer, nullable=False, default=0)  # Количество оставшихся посещений
    
    # Связи
    user = relationship("User", back_populates="abonement")
    
    def __repr__(self):
        return f"<Abonement(id={self.id}, user_id={self.user_id}, visits_left={self.visits_left})>"


class Booking(Base):
    """
    Модель для хранения информации о бронированиях.
    """
    __tablename__ = 'bookings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Внешний ключ к User.id
    start_time = Column(DateTime, nullable=False)  # Время начала бронирования
    end_time = Column(DateTime, nullable=False)  # Время окончания бронирования
    
    # Связи
    user = relationship("User", back_populates="bookings")
    
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


async def get_or_create_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> Optional[User]:
    """
    Атомарно находит пользователя по telegram_id или создает нового, если он не найден.
    
    Args:
        telegram_id: ID пользователя в Telegram
        username: Имя пользователя в Telegram (может быть None)
        first_name: Имя пользователя (может быть None)
    
    Returns:
        User: Объект пользователя или None в случае ошибки
    """
    try:
        async with async_session() as session:
            from sqlalchemy import select
            
            # Ищем существующего пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                # Создаем нового пользователя
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name
                )
                session.add(user)
                await session.flush()  # Получаем ID пользователя
                
                # Создаем абонемент для нового пользователя
                abonement = Abonement(
                    user_id=user.id,
                    visits_left=0
                )
                session.add(abonement)
                await session.commit()
                
                print(f"Создан новый пользователь: {user}")
            else:
                # Обновляем информацию о пользователе, если она изменилась
                if user.username != username or user.first_name != first_name:
                    user.username = username
                    user.first_name = first_name
                    await session.commit()
                    print(f"Обновлена информация о пользователе: {user}")
            
            return user
            
    except Exception as e:
        print(f"Ошибка при получении/создании пользователя: {e}")
        return None


async def get_user_abonement(user_id: int) -> Optional[Abonement]:
    """
    Находит и возвращает абонемент пользователя.
    
    Args:
        user_id: ID пользователя в базе данных
    
    Returns:
        Abonement: Объект абонемента или None если не найден
    """
    try:
        async with async_session() as session:
            from sqlalchemy import select
            
            result = await session.execute(
                select(Abonement).where(Abonement.user_id == user_id)
            )
            abonement = result.scalar_one_or_none()
            
            return abonement
            
    except Exception as e:
        print(f"Ошибка при получении абонемента: {e}")
        return None


async def decrease_user_visits(user_id: int) -> bool:
    """
    Уменьшает visits_left на 1. Безопасная функция, не уводит счетчик в минус.
    
    Args:
        user_id: ID пользователя в базе данных
    
    Returns:
        bool: True если посещение успешно списано, False если посещений нет или ошибка
    """
    try:
        async with async_session() as session:
            from sqlalchemy import select
            
            result = await session.execute(
                select(Abonement).where(Abonement.user_id == user_id)
            )
            abonement = result.scalar_one_or_none()
            
            if abonement is None or abonement.visits_left <= 0:
                return False
            
            abonement.visits_left -= 1
            await session.commit()
            
            print(f"Списано посещение для пользователя {user_id}. Осталось: {abonement.visits_left}")
            return True
            
    except Exception as e:
        print(f"Ошибка при списании посещения: {e}")
        return False


async def add_user_visits(user_id: int, count: int) -> bool:
    """
    Увеличивает visits_left на count. Используется для начисления купленных абонементов.
    
    Args:
        user_id: ID пользователя в базе данных
        count: Количество посещений для добавления
    
    Returns:
        bool: True если посещения успешно добавлены, False в случае ошибки
    """
    try:
        async with async_session() as session:
            from sqlalchemy import select
            
            result = await session.execute(
                select(Abonement).where(Abonement.user_id == user_id)
            )
            abonement = result.scalar_one_or_none()
            
            if abonement is None:
                # Создаем абонемент, если его нет
                abonement = Abonement(
                    user_id=user_id,
                    visits_left=count
                )
                session.add(abonement)
            else:
                abonement.visits_left += count
            
            await session.commit()
            
            print(f"Добавлено {count} посещений для пользователя {user_id}. Всего: {abonement.visits_left}")
            return True
            
    except Exception as e:
        print(f"Ошибка при добавлении посещений: {e}")
        return False


async def add_booking(user_id: int, start_time: datetime, end_time: datetime) -> bool:
    """
    Добавляет новое бронирование в базу данных.
    
    Args:
        user_id: ID пользователя в базе данных (внешний ключ)
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
        user_id: ID пользователя в базе данных
    
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
    
    # Создаем тестового пользователя
    user = await get_or_create_user(12345, "test_user", "Test User")
    if user:
        print(f"Тестовый пользователь: {user}")
        
        # Добавляем посещения
        await add_user_visits(user.id, 5)
        
        # Тестовое бронирование
        test_start = datetime.now() + timedelta(days=1)
        test_end = test_start + timedelta(hours=2)
        
        success = await add_booking(user.id, test_start, test_end)
        print(f"Тестовое бронирование добавлено: {success}")
        
        bookings = await get_user_bookings(user.id)
        print(f"Бронирования пользователя: {bookings}")
        
        # Проверяем абонемент
        abonement = await get_user_abonement(user.id)
        print(f"Абонемент пользователя: {abonement}")
    
    await close_database()


if __name__ == "__main__":
    # Запуск тестирования
    asyncio.run(test_database())
