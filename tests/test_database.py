import asyncio
import os
import pytest
from datetime import datetime, timedelta, time as dtime

from database import init_database, async_session, add_booking, get_or_create_user, has_booking_on_date


@pytest.mark.asyncio
async def test_has_booking_on_date(tmp_path, monkeypatch):
    # Ensure DB file used is temporary to avoid clobbering real data
    db_file = tmp_path / "test_bookings.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # Initialize an isolated test DB
    await init_database(db_url=db_url)

    # Create or get a test user
    user = await get_or_create_user(99999999, "testuser", "Test")
    assert user is not None

    # Create a booking for today at 12:00 for 1 hour
    today = datetime.now().date()
    start = datetime.combine(today, dtime(12, 0))
    end = start + timedelta(hours=1)

    booking = await add_booking(user.id, start, end)
    assert booking is not None

    # Now check has_booking_on_date
    has = await has_booking_on_date(user.id, today)
    assert has is True
