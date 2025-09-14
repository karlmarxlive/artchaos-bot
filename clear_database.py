"""
Скрипт для полной очистки базы данных.
Удаляет все данные из всех таблиц: users, abonements, bookings.
"""

import asyncio
import os
from sqlalchemy import text
from database import init_database, close_database, engine


async def clear_all_tables():
    """
    Очищает все таблицы в базе данных.
    """
    try:
        # Инициализируем подключение к базе данных
        await init_database()
        
        print("🔄 Начинаем очистку базы данных...")
        
        # Получаем список всех таблиц
        async with engine.begin() as conn:
            # Получаем список таблиц
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            
            print(f"📋 Найдены таблицы: {', '.join(tables)}")
            
            # Отключаем проверку внешних ключей для безопасного удаления
            await conn.execute(text("PRAGMA foreign_keys = OFF"))
            
            # Очищаем каждую таблицу
            for table in tables:
                if table != 'sqlite_sequence':  # Пропускаем системную таблицу
                    await conn.execute(text(f"DELETE FROM {table}"))
                    print(f"✅ Таблица '{table}' очищена")
            
            # Сбрасываем автоинкремент для всех таблиц
            await conn.execute(text("DELETE FROM sqlite_sequence"))
            print("✅ Автоинкремент сброшен")
            
            # Включаем обратно проверку внешних ключей
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            
        print("🎉 База данных успешно очищена!")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке базы данных: {e}")
    finally:
        # Закрываем соединение
        await close_database()


async def clear_database_with_confirmation():
    """
    Очищает базу данных с подтверждением пользователя.
    """
    print("⚠️  ВНИМАНИЕ: Этот скрипт удалит ВСЕ данные из базы данных!")
    print("📊 Будут удалены:")
    print("   - Все пользователи (users)")
    print("   - Все абонементы (abonements)")
    print("   - Все бронирования (bookings)")
    print()
    
    # Проверяем существование файла базы данных
    if not os.path.exists("bookings.db"):
        print("❌ Файл базы данных 'bookings.db' не найден!")
        return
    
    # Получаем размер файла базы данных
    db_size = os.path.getsize("bookings.db")
    print(f"📁 Размер файла базы данных: {db_size} байт")
    print()
    
    # Запрашиваем подтверждение
    confirmation = input("❓ Вы уверены, что хотите очистить базу данных? (да/нет): ").lower().strip()
    
    if confirmation in ['да', 'yes', 'y', 'д']:
        await clear_all_tables()
    else:
        print("❌ Очистка отменена.")


async def show_database_stats():
    """
    Показывает статистику базы данных перед очисткой.
    """
    try:
        await init_database()
        
        print("📊 Статистика базы данных:")
        print("-" * 40)
        
        async with engine.begin() as conn:
            # Подсчитываем количество записей в каждой таблице
            tables_to_check = ['users', 'abonements', 'bookings']
            
            for table in tables_to_check:
                try:
                    result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"📋 {table}: {count} записей")
                except Exception as e:
                    print(f"❌ Ошибка при подсчете записей в таблице {table}: {e}")
        
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ Ошибка при получении статистики: {e}")
    finally:
        await close_database()


if __name__ == "__main__":
    print("🗑️  Скрипт очистки базы данных ArtChaos Bot")
    print("=" * 50)
    
    # Показываем статистику
    asyncio.run(show_database_stats())
    print()
    
    # Запускаем очистку с подтверждением
    asyncio.run(clear_database_with_confirmation())
