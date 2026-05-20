import datetime

import aiosqlite

DB_PATH = "botdata.db"


async def init_db():
    """Initialisiert die Datenbank und erstellt die Tabelle, falls sie nicht existiert."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Enable Write-Ahead Logging for better concurrency
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                user_id INTEGER PRIMARY KEY,
                correct_answers INTEGER NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0,
                last_activity DATE
            )
        """)

        # Daily quests table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_quests (
                user_id INTEGER PRIMARY KEY,
                quest_date DATE NOT NULL,
                quizzes_completed INTEGER NOT NULL DEFAULT 0,
                voted_today INTEGER NOT NULL DEFAULT 0,
                quest_completed INTEGER NOT NULL DEFAULT 0,
                streak_freezes INTEGER NOT NULL DEFAULT 0,
                bonus_hints INTEGER NOT NULL DEFAULT 0,
                saves REAL NOT NULL DEFAULT 0
            )
        """)

        # Check for missing columns in daily_quests (lightweight migrations)
        cursor = await db.execute("PRAGMA table_info(daily_quests)")
        dq_columns = [row[1] async for row in cursor]

        # Very old DBs may miss the legacy `saves` column.
        if "saves" not in dq_columns:
            await db.execute(
                "ALTER TABLE daily_quests ADD COLUMN saves REAL NOT NULL DEFAULT 0"
            )
            dq_columns.append("saves")

        # Inventory balances stored as integer tenths to avoid float drift.
        # 10 units = 1.0 item. Rewards: +0.2 freeze = +2 units, +0.5 save = +5 units.
        if "streak_freeze_units" not in dq_columns:
            await db.execute(
                "ALTER TABLE daily_quests ADD COLUMN streak_freeze_units INTEGER NOT NULL DEFAULT 0"
            )
            # Migrate existing integer streak_freezes -> units (best effort)
            await db.execute(
                "UPDATE daily_quests SET streak_freeze_units = COALESCE(streak_freezes, 0) * 10"
            )

        if "save_units" not in dq_columns:
            await db.execute(
                "ALTER TABLE daily_quests ADD COLUMN save_units INTEGER NOT NULL DEFAULT 0"
            )
            # Migrate existing saves (REAL) -> units (best effort)
            await db.execute(
                "UPDATE daily_quests SET save_units = CAST(ROUND(COALESCE(saves, 0) * 10) AS INTEGER)"
            )

        # New daily quest: count 5 numbers in the counting channel.
        if "counting_numbers" not in dq_columns:
            await db.execute(
                "ALTER TABLE daily_quests ADD COLUMN counting_numbers INTEGER NOT NULL DEFAULT 0"
            )

        # Track individual completion of each quest so rewards are granted per-quest.
        if "quiz_quest_completed" not in dq_columns:
            await db.execute(
                "ALTER TABLE daily_quests ADD COLUMN quiz_quest_completed INTEGER NOT NULL DEFAULT 0"
            )

        if "counting_quest_completed" not in dq_columns:
            await db.execute(
                "ALTER TABLE daily_quests ADD COLUMN counting_quest_completed INTEGER NOT NULL DEFAULT 0"
            )

        # Keep the old columns around for backward compatibility (streak_freezes/saves),
        # but new code reads/writes *_units.

        # Weekly leaderboard table
        # Note: user_id is NOT a primary key here because we might want to store history,
        # or at least we need (user_id, week_start) to be unique.
        # Since we can't easily alter PK in sqlite, we'll just create it correctly if not exists.
        # If it exists with wrong schema, we might need to drop it.

        # Check if table exists and has correct schema (simple check)
        cursor = await db.execute("PRAGMA table_info(weekly_leaderboard)")
        columns = await cursor.fetchall()

        # If table exists but user_id is the single PK, we should probably recreate it.
        # For now, let's just try to create it if not exists with a composite PK.
        # But since the user likely already has the wrong table, we will DROP it if it exists
        # to ensure the schema is correct. This is a one-time migration for this integration.

        # We will check if we need to migrate by checking if we can insert a duplicate user_id
        # or just by checking the PK definition.
        # Simplest way for this context: Drop and recreate if it's the old schema.

        # Let's just use INSERT OR REPLACE in update_weekly_score instead of relying on complex schema changes
        # if we want to avoid dropping data. But dropping is cleaner for "integration".

        # Let's try to create with composite primary key.
        # If the table was created by the previous run with `user_id INTEGER PRIMARY KEY`,
        # we should drop it to fix the schema.

        # Check if user_id is the only PK
        is_bad_schema = False
        if columns:
            # columns is list of (cid, name, type, notnull, dflt_value, pk)
            # pk > 0 means it is part of primary key.
            pk_cols = [c[1] for c in columns if c[5] > 0]
            if len(pk_cols) == 1 and pk_cols[0] == "user_id":
                is_bad_schema = True

        if is_bad_schema:
            print("Migrating weekly_leaderboard schema...")
            await db.execute("DROP TABLE weekly_leaderboard")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_leaderboard (
                user_id INTEGER,
                weekly_score INTEGER NOT NULL DEFAULT 0,
                week_start DATE NOT NULL,
                week_end DATE NOT NULL,
                PRIMARY KEY (user_id, week_start)
            )
        """)

        # Counting game tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS counting_config (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                current_count INTEGER NOT NULL DEFAULT 0,
                last_user_id INTEGER,
                high_score INTEGER NOT NULL DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS counting_stats (
                user_id INTEGER,
                guild_id INTEGER,
                total_counts INTEGER NOT NULL DEFAULT 0,
                ruined_counts INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        """)

        # Guild save pool for counting mistakes.
        # Stored as tenths (10 units = 1.0 save).
        await db.execute("""
            CREATE TABLE IF NOT EXISTS counting_guild_saves (
                guild_id INTEGER PRIMARY KEY,
                save_units INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Per-guild daily counting tracker.
        # Tracks how many valid counting numbers have been posted in a guild for the current day.
        # When a guild reaches every 10 counts in a single day, the guild is awarded 1.0 save (10 units).
        await db.execute("""
            CREATE TABLE IF NOT EXISTS counting_guild_daily (
                guild_id INTEGER PRIMARY KEY,
                date DATE NOT NULL,
                count INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Truth or Dare table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tod_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                question TEXT NOT NULL,
                rating TEXT DEFAULT 'PG'
            )
        """)

        # Check if TOD table is empty, if so populate it
        async with db.execute("SELECT COUNT(*) FROM tod_questions") as cursor:
            count = await cursor.fetchone()
            if count and count[0] == 0:
                await populate_tod_questions(db)

        await db.commit()
        await migrate_leaderboard()  # Prüft und fügt fehlende Spalten hinzu


MAX_STREAK_FREEZE_UNITS = 20  # 2.0
MAX_SAVE_UNITS = 40  # 4.0
USE_ITEM_UNITS = 10  # 1.0
QUEST_REWARD_FREEZE_UNITS = 2  # 0.2
QUEST_REWARD_SAVE_UNITS = 5  # 0.5


def _coerce_date(value: object) -> datetime.date:
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            pass
    return datetime.date.today()


def _clamp_int(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, int(value)))


def _format_units(units: int) -> str:
    # Display with at most 1 decimal (units are tenths).
    whole, tenth = divmod(int(units), 10)
    if tenth == 0:
        return str(whole)
    return f"{whole}.{tenth}"


async def _ensure_daily_quest_row(db: aiosqlite.Connection, user_id: int) -> None:
    today = datetime.date.today()

    # Ensure row exists
    await db.execute(
        """
        INSERT OR IGNORE INTO daily_quests (
            user_id, quest_date,
            quizzes_completed, counting_numbers,
            quiz_quest_completed, counting_quest_completed,
            voted_today, quest_completed,
            streak_freezes, bonus_hints, saves,
            streak_freeze_units, save_units
        )
        VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        """,
        (user_id, today),
    )

    # Reset daily progress if date has rolled over
    cursor = await db.execute(
        "SELECT quest_date FROM daily_quests WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    quest_date = _coerce_date(row[0]) if row else today
    if quest_date < today:
        await db.execute(
            """
            UPDATE daily_quests
            SET quest_date = ?,
                quizzes_completed = 0,
                counting_numbers = 0,
                quiz_quest_completed = 0,
                counting_quest_completed = 0,
                voted_today = 0,
                quest_completed = 0
            WHERE user_id = ?
            """,
            (today, user_id),
        )


async def populate_tod_questions(db):
    """Populate the TOD table with default questions."""
    truths = [
        "What is your biggest fear?",
        "What is the most embarrassing thing you have ever done?",
        "What is your biggest secret?",
        "Who is your secret crush?",
        "What is the worst lie you have ever told?",
        "What is your most regretful purchase?",
        "What is the most trouble you have ever been in?",
        "What is your favorite holiday and why?",
        "What is your dream job?",
        "If you could be any animal, what would you be?",
        "What is your favorite movie?",
        "What is your favorite song?",
        "What is your favorite food?",
        "What is your favorite color?",
        "What is your favorite hobby?",
        "Have you ever cheated on a test?",
        "Have you ever peed in a pool?",
        "Have you ever broken a bone?",
        "Have you ever been to another country?",
        "Have you ever met a celebrity?",
    ]

    dares = [
        "Do 10 pushups.",
        "Sing a song.",
        "Dance for 1 minute.",
        "Tell a joke.",
        "Do an impression of someone.",
        "Speak in an accent for the next 3 rounds.",
        "Let someone else style your hair.",
        "Eat a spoonful of mustard.",
        "Drink a glass of water without using your hands.",
        "Balance a spoon on your nose for 10 seconds.",
        "Walk backwards for the next 3 rounds.",
        "Don't blink for 30 seconds.",
        "Hold your breath for 30 seconds.",
        "Spin around 10 times and try to walk in a straight line.",
        "Do a cartwheel.",
        "Do a handstand.",
        "Touch your toes.",
        "Lick your elbow.",
        "Wiggle your ears.",
        "Raise one eyebrow.",
    ]

    for t in truths:
        await db.execute(
            "INSERT INTO tod_questions (type, question) VALUES (?, ?)", ("truth", t)
        )

    for d in dares:
        await db.execute(
            "INSERT INTO tod_questions (type, question) VALUES (?, ?)", ("dare", d)
        )


async def migrate_leaderboard():
    """Fügt fehlende Spalten hinzu, falls die Tabelle schon existierte ohne diese Spalten."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(leaderboard)")
        columns = [row[1] async for row in cursor]

        if "streak" not in columns:
            await db.execute(
                "ALTER TABLE leaderboard ADD COLUMN streak INTEGER NOT NULL DEFAULT 0"
            )
        if "best_streak" not in columns:
            await db.execute(
                "ALTER TABLE leaderboard ADD COLUMN best_streak INTEGER NOT NULL DEFAULT 0"
            )
        if "last_activity" not in columns:
            await db.execute("ALTER TABLE leaderboard ADD COLUMN last_activity DATE")
        await db.commit()


def get_current_week():
    """Returns the start and end date of the current week (Monday to Sunday)."""
    today = datetime.date.today()
    days_since_monday = today.weekday()
    week_start = today - datetime.timedelta(days=days_since_monday)
    week_end = week_start + datetime.timedelta(days=6)
    return week_start, week_end


async def update_weekly_score(user_id: int, points: int = 1):
    """Updates weekly score for a user."""
    week_start, week_end = get_current_week()

    async with aiosqlite.connect(DB_PATH) as db:
        # Check if user has entry for current week
        cursor = await db.execute(
            "SELECT weekly_score FROM weekly_leaderboard WHERE user_id = ? AND week_start = ?",
            (user_id, week_start),
        )
        row = await cursor.fetchone()

        if row:
            # Update existing weekly score
            new_score = row[0] + points
            await db.execute(
                "UPDATE weekly_leaderboard SET weekly_score = ? WHERE user_id = ? AND week_start = ?",
                (new_score, user_id, week_start),
            )
        else:
            # Create new weekly entry
            await db.execute(
                "INSERT INTO weekly_leaderboard (user_id, weekly_score, week_start, week_end) VALUES (?, ?, ?, ?)",
                (user_id, points, week_start, week_end),
            )
        await db.commit()


async def reset_weekly_leaderboard():
    """Resets weekly leaderboard for new week."""
    week_start, week_end = get_current_week()

    async with aiosqlite.connect(DB_PATH) as db:
        # Delete old weekly entries (older than current week)
        await db.execute(
            "DELETE FROM weekly_leaderboard WHERE week_start < ?", (week_start,)
        )
        await db.commit()


async def get_weekly_leaderboard(limit=10):
    """Gets current weekly leaderboard."""
    week_start, week_end = get_current_week()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, weekly_score FROM weekly_leaderboard WHERE week_start = ? ORDER BY weekly_score DESC LIMIT ?",
            (week_start, limit),
        )
        return await cursor.fetchall()


async def get_streak_leaderboard(limit=10):
    """Gets leaderboard sorted by current streak."""
    # await migrate_leaderboard() # Removed to prevent overhead/locking, called in init_db
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, streak, best_streak FROM leaderboard WHERE streak > 0 ORDER BY streak DESC, best_streak DESC LIMIT ?",
            (limit,),
        )
        return await cursor.fetchall()


async def update_user_activity(user_id: int):
    """Updates last activity date for streak tracking."""
    today = datetime.date.today()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE leaderboard SET last_activity = ? WHERE user_id = ?",
            (today, user_id),
        )
        await db.commit()


async def increment_user_score(
    user_id: int, points: int = 1, reset_streak: bool = False
):
    """Erhöht den Score eines Users und aktualisiert Streaks."""
    # await migrate_leaderboard()
    today = datetime.date.today()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT correct_answers, streak, best_streak, last_activity FROM leaderboard WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            current_score, current_streak, best_streak, last_activity = row

            # Check if streak should be reset due to missed days
            if last_activity:
                last_date = datetime.datetime.strptime(last_activity, "%Y-%m-%d").date()
                days_diff = (today - last_date).days
                if days_diff > 1:  # More than 1 day gap resets streak
                    reset_streak = True

            new_streak = 1 if reset_streak else current_streak + 1
            best_streak = max(best_streak, new_streak)
            new_score = current_score + points
            await db.execute(
                "UPDATE leaderboard SET correct_answers = ?, streak = ?, best_streak = ?, last_activity = ? WHERE user_id = ?",
                (new_score, new_streak, best_streak, today, user_id),
            )
        else:
            streak = 1 if reset_streak else 1
            best_streak = streak
            await db.execute(
                "INSERT INTO leaderboard (user_id, correct_answers, streak, best_streak, last_activity) VALUES (?, ?, ?, ?, ?)",
                (user_id, points, streak, best_streak, today),
            )
        await db.commit()

    # Also update weekly score
    await update_weekly_score(user_id, points)


async def reset_user_streak(user_id: int):
    """Setzt die aktuelle Streak eines Users auf 0 zurück."""
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE leaderboard SET streak = 0 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def get_leaderboard(limit=10):
    """Gibt die Top-N User nach korrekt beantworteten Fragen zurück."""
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, correct_answers, streak, best_streak FROM leaderboard ORDER BY correct_answers DESC LIMIT ?",
            (limit,),
        )
        return await cursor.fetchall()


async def get_user_stats(user_id: int):
    """Gibt die Stats (score, streak, best_streak) für einen bestimmten User zurück."""
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT correct_answers, streak, best_streak FROM leaderboard WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return row  # (score, streak, best_streak)
        else:
            # Wenn der User noch nie gespielt hat: alles auf 0
            return (0, 0, 0)


async def get_user_rank(user_id: int):
    """Gibt den Rang des Users im Leaderboard zurück (1 = bester)."""
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        # Zuerst Score holen
        cursor = await db.execute(
            "SELECT correct_answers FROM leaderboard WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None  # User existiert nicht in DB
        score = row[0]

        # Rang berechnen: alle User zählen, die mehr Punkte haben
        cursor = await db.execute(
            "SELECT COUNT(*) FROM leaderboard WHERE correct_answers > ?", (score,)
        )
        row = await cursor.fetchone()
        higher_count = row[0] if row is not None else 0
        return higher_count + 1


async def get_score_gap(user_id: int):
    """
    Gibt die Punkte-Differenz und User-ID des nächsthöheren Spielers zurück.
    Rückgabe: (gap, higher_user_id) oder (None, None) falls man Erster ist.
    """
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        # Eigenen Score holen
        cursor = await db.execute(
            "SELECT correct_answers FROM leaderboard WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None, None
        score = row[0]

        # Nächsthöheren Score + User-ID finden
        cursor = await db.execute(
            "SELECT user_id, correct_answers FROM leaderboard WHERE correct_answers > ? ORDER BY correct_answers ASC LIMIT 1",
            (score,),
        )
        higher = await cursor.fetchone()
        if higher:
            higher_id, higher_score = higher
            return higher_score - score, higher_id
        else:
            return None, None  # Kein höherer Spieler = User ist #1


# ========== Daily Quests Functions ==========


async def get_daily_quest_progress(user_id: int):
    """
    Get the daily quest progress for a user.
    Returns: (quest_date, quizzes_completed, counting_numbers, quiz_completed, counting_completed, streak_freeze_units, save_units)
    """
    today = datetime.date.today()

    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)

        cursor = await db.execute(
            """
            SELECT quest_date,
                   quizzes_completed,
                   counting_numbers,
                   quiz_quest_completed,
                   counting_quest_completed,
                   streak_freeze_units,
                   save_units
            FROM daily_quests
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return (today, 0, 0, 0, 0, 0, 0)

        quest_date = _coerce_date(row[0])
        quizzes = int(row[1] or 0)
        counting_numbers = int(row[2] or 0)
        quiz_done = int(row[3] or 0)
        counting_done = int(row[4] or 0)
        freeze_units = int(row[5] or 0)
        save_units = int(row[6] or 0)

        return (
            quest_date,
            quizzes,
            counting_numbers,
            quiz_done,
            counting_done,
            freeze_units,
            save_units,
        )


async def increment_quest_quiz_count(user_id: int):
    """
    Increment the quiz task progress for today's quest.
    Returns True if the *quiz quest* was completed with this answer.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)

        cursor = await db.execute(
            """
            SELECT quizzes_completed, quiz_quest_completed, streak_freeze_units, save_units
            FROM daily_quests
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        quizzes = int(row[0] or 0) if row else 0
        quest_done = int(row[1] or 0) if row else 0
        freeze_units = int(row[2] or 0) if row else 0
        save_units = int(row[3] or 0) if row else 0

        if quest_done == 1:
            return False

        if quizzes >= 5:
            return False

        new_quizzes = min(5, quizzes + 1)
        quest_complete = new_quizzes >= 5

        if quest_complete:
            new_freeze_units = _clamp_int(
                freeze_units + QUEST_REWARD_FREEZE_UNITS, 0, MAX_STREAK_FREEZE_UNITS
            )
            new_save_units = _clamp_int(
                save_units + QUEST_REWARD_SAVE_UNITS, 0, MAX_SAVE_UNITS
            )
            await db.execute(
                """
                UPDATE daily_quests
                SET quizzes_completed = ?,
                    quiz_quest_completed = 1,
                    streak_freeze_units = ?,
                    save_units = ?
                WHERE user_id = ?
                """,
                (new_quizzes, new_freeze_units, new_save_units, user_id),
            )
        else:
            await db.execute(
                "UPDATE daily_quests SET quizzes_completed = ? WHERE user_id = ?",
                (new_quizzes, user_id),
            )

        await db.commit()
        return quest_complete


async def increment_quest_counting_count(user_id: int):
    """Increment the counting task progress for today's quest.

    Returns True if the *counting quest* was completed with this count.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)

        cursor = await db.execute(
            """
            SELECT counting_numbers, counting_quest_completed, streak_freeze_units, save_units
            FROM daily_quests
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        counted = int(row[0] or 0) if row else 0
        quest_done = int(row[1] or 0) if row else 0
        freeze_units = int(row[2] or 0) if row else 0
        save_units = int(row[3] or 0) if row else 0

        if quest_done == 1:
            return False

        if counted >= 5:
            return False

        new_counted = min(5, counted + 1)
        quest_complete = new_counted >= 5

        if quest_complete:
            new_freeze_units = _clamp_int(
                freeze_units + QUEST_REWARD_FREEZE_UNITS, 0, MAX_STREAK_FREEZE_UNITS
            )
            new_save_units = _clamp_int(
                save_units + QUEST_REWARD_SAVE_UNITS, 0, MAX_SAVE_UNITS
            )
            await db.execute(
                """
                UPDATE daily_quests
                SET counting_numbers = ?,
                    counting_quest_completed = 1,
                    streak_freeze_units = ?,
                    save_units = ?
                WHERE user_id = ?
                """,
                (new_counted, new_freeze_units, new_save_units, user_id),
            )
        else:
            await db.execute(
                "UPDATE daily_quests SET counting_numbers = ? WHERE user_id = ?",
                (new_counted, user_id),
            )

        await db.commit()
        return quest_complete


async def mark_quest_voted(user_id: int):
    """
    Mark that the user has voted today.
    Legacy helper (voting quest not currently used).

    Returns False.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)

        # Keep a flag for future use; do not award items from voting.
        await db.execute(
            "UPDATE daily_quests SET voted_today = 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return False


async def use_streak_freeze(user_id: int):
    """
    Use a streak freeze to prevent streak reset.
    Returns True if freeze was available and used.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)

        cursor = await db.execute(
            "SELECT streak_freeze_units FROM daily_quests WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()

        current_units = int(row[0] or 0) if row else 0
        if current_units < USE_ITEM_UNITS:
            return False

        await db.execute(
            "UPDATE daily_quests SET streak_freeze_units = streak_freeze_units - ? WHERE user_id = ?",
            (USE_ITEM_UNITS, user_id),
        )
        await db.commit()
        return True


async def use_bonus_hint(user_id: int):
    """
    Use a bonus hint for a quiz.
    Returns True if hint was available and used.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT bonus_hints FROM daily_quests WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()

        if not row or row[0] <= 0:
            return False

        # Use one hint
        await db.execute(
            "UPDATE daily_quests SET bonus_hints = bonus_hints - 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return True


async def get_quest_rewards(user_id: int):
    """
    Get the current inventory balances.
    Returns: (streak_freeze_units, save_units)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)
        cursor = await db.execute(
            "SELECT streak_freeze_units, save_units FROM daily_quests WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return (0, 0)
        return (int(row[0] or 0), int(row[1] or 0))


async def get_user_save_units(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)
        cursor = await db.execute(
            "SELECT save_units FROM daily_quests WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return int(row[0] or 0) if row else 0


async def try_use_user_save(user_id: int) -> bool:
    """Consume 1.0 personal save if available."""
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_daily_quest_row(db, user_id)
        cursor = await db.execute(
            "SELECT save_units FROM daily_quests WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        units = int(row[0] or 0) if row else 0
        if units < USE_ITEM_UNITS:
            return False
        await db.execute(
            "UPDATE daily_quests SET save_units = save_units - ? WHERE user_id = ?",
            (USE_ITEM_UNITS, user_id),
        )
        await db.commit()
        return True


async def get_guild_save_units(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT save_units FROM counting_guild_saves WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        return int(row[0] or 0) if row else 0


async def add_guild_save_units(guild_id: int, units: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO counting_guild_saves (guild_id, save_units)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET save_units = save_units + excluded.save_units
            """,
            (guild_id, int(units)),
        )
        await db.commit()
        return await get_guild_save_units(guild_id)


async def try_use_guild_save(guild_id: int) -> bool:
    """Consume 1.0 guild save if available."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT save_units FROM counting_guild_saves WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        units = int(row[0] or 0) if row else 0
        if units < USE_ITEM_UNITS:
            return False
        await db.execute(
            "UPDATE counting_guild_saves SET save_units = save_units - ? WHERE guild_id = ?",
            (USE_ITEM_UNITS, guild_id),
        )
        await db.commit()
        return True


async def get_guild_daily_count(guild_id: int) -> int:
    """
    Return the number of valid counting numbers recorded for the given guild for today.
    If no row exists or the stored date is older than today, returns 0.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT count, date FROM counting_guild_daily WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return 0
        row_count = int(row[0] or 0)
        row_date = _coerce_date(row[1])
        if row_date < datetime.date.today():
            return 0
        return row_count


async def increment_guild_daily_count(guild_id: int):
    """
    Increment the daily count for the given guild by 1.

    Returns a tuple (awarded_save: bool, new_count: int):
      - awarded_save is True if this increment caused the guild to reach a multiple of 10 counts
        for the day and a 1.0 save (10 units) was awarded to the guild.
      - new_count is the updated count for today after this increment.

    Notes:
      - This uses the counting_guild_daily table to track per-guild daily counts and will reset
        the counter automatically when the stored date is older than today.
      - When a multiple of 10 is reached (10, 20, 30, ...), the guild is awarded 10 units
        (i.e., 1.0 save) via add_guild_save_units.
    """
    today = datetime.date.today()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT count, date FROM counting_guild_daily WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        if not row:
            new_count = 1
            await db.execute(
                "INSERT INTO counting_guild_daily (guild_id, date, count) VALUES (?, ?, ?)",
                (guild_id, today, new_count),
            )
        else:
            row_count = int(row[0] or 0)
            row_date = _coerce_date(row[1])
            if row_date < today:
                new_count = 1
                await db.execute(
                    "UPDATE counting_guild_daily SET date = ?, count = ? WHERE guild_id = ?",
                    (today, new_count, guild_id),
                )
            else:
                new_count = row_count + 1
                await db.execute(
                    "UPDATE counting_guild_daily SET count = ? WHERE guild_id = ?",
                    (new_count, guild_id),
                )

        await db.commit()

    awarded = False
    if new_count % 10 == 0:
        # Award 1.0 guild save (10 units).
        await add_guild_save_units(guild_id, 10)
        awarded = True

    return awarded, new_count
