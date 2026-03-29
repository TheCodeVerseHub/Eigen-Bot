import aiosqlite
import datetime

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
        
        # Check for missing columns in daily_quests
        cursor = await db.execute("PRAGMA table_info(daily_quests)")
        dq_columns = [row[1] async for row in cursor]
        if "saves" not in dq_columns:
            await db.execute("ALTER TABLE daily_quests ADD COLUMN saves REAL NOT NULL DEFAULT 0")
        
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
            if len(pk_cols) == 1 and pk_cols[0] == 'user_id':
                is_bad_schema = True
        
        if is_bad_schema:
            print(f"[Database] Notice: Migrating 'weekly_leaderboard' to a new schema. Recreating table with a composite Primary Key (user_id, week_start) to support multi-week history.")
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
        "Have you ever met a celebrity?"
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
        "Raise one eyebrow."
    ]
    
    for t in truths:
        await db.execute("INSERT INTO tod_questions (type, question) VALUES (?, ?)", ("truth", t))
    
    for d in dares:
        await db.execute("INSERT INTO tod_questions (type, question) VALUES (?, ?)", ("dare", d))

async def migrate_leaderboard():
    """Fügt fehlende Spalten hinzu, falls die Tabelle schon existierte ohne diese Spalten."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(leaderboard)")
        columns = [row[1] async for row in cursor]

        if "streak" not in columns:
            await db.execute("ALTER TABLE leaderboard ADD COLUMN streak INTEGER NOT NULL DEFAULT 0")
        if "best_streak" not in columns:
            await db.execute("ALTER TABLE leaderboard ADD COLUMN best_streak INTEGER NOT NULL DEFAULT 0")
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
            (user_id, week_start)
        )
        row = await cursor.fetchone()
        
        if row:
            # Update existing weekly score
            new_score = row[0] + points
            await db.execute(
                "UPDATE weekly_leaderboard SET weekly_score = ? WHERE user_id = ? AND week_start = ?",
                (new_score, user_id, week_start)
            )
        else:
            # Create new weekly entry
            await db.execute(
                "INSERT INTO weekly_leaderboard (user_id, weekly_score, week_start, week_end) VALUES (?, ?, ?, ?)",
                (user_id, points, week_start, week_end)
            )
        await db.commit()

async def reset_weekly_leaderboard():
    """Resets weekly leaderboard for new week."""
    week_start, week_end = get_current_week()
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Delete old weekly entries (older than current week)
        await db.execute(
            "DELETE FROM weekly_leaderboard WHERE week_start < ?",
            (week_start,)
        )
        await db.commit()

async def get_weekly_leaderboard(limit=10):
    """Gets current weekly leaderboard."""
    week_start, week_end = get_current_week()
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, weekly_score FROM weekly_leaderboard WHERE week_start = ? ORDER BY weekly_score DESC LIMIT ?",
            (week_start, limit)
        )
        return await cursor.fetchall()

async def get_streak_leaderboard(limit=10):
    """Gets leaderboard sorted by current streak."""
    # await migrate_leaderboard() # Removed to prevent overhead/locking, called in init_db
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, streak, best_streak FROM leaderboard WHERE streak > 0 ORDER BY streak DESC, best_streak DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()

async def update_user_activity(user_id: int):
    """Updates last activity date for streak tracking."""
    today = datetime.date.today()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE leaderboard SET last_activity = ? WHERE user_id = ?",
            (today, user_id)
        )
        await db.commit()

async def increment_user_score(user_id: int, points: int = 1, reset_streak: bool = False):
    """Erhöht den Score eines Users und aktualisiert Streaks."""
    # await migrate_leaderboard()
    today = datetime.date.today()
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT correct_answers, streak, best_streak, last_activity FROM leaderboard WHERE user_id = ?", 
            (user_id,)
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
                (new_score, new_streak, best_streak, today, user_id)
            )
        else:
            streak = 1 if reset_streak else 1
            best_streak = streak
            await db.execute(
                "INSERT INTO leaderboard (user_id, correct_answers, streak, best_streak, last_activity) VALUES (?, ?, ?, ?, ?)",
                (user_id, points, streak, best_streak, today)
            )
        await db.commit()
    
    # Also update weekly score
    await update_weekly_score(user_id, points)

async def reset_user_streak(user_id: int):
    """Setzt die aktuelle Streak eines Users auf 0 zurück."""
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE leaderboard SET streak = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_leaderboard(limit=10):
    """Gibt die Top-N User nach korrekt beantworteten Fragen zurück."""
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, correct_answers, streak, best_streak FROM leaderboard ORDER BY correct_answers DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()
    
async def get_user_stats(user_id: int):
    """Gibt die Stats (score, streak, best_streak) für einen bestimmten User zurück."""
    # await migrate_leaderboard()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT correct_answers, streak, best_streak FROM leaderboard WHERE user_id = ?",
            (user_id,)
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
            "SELECT correct_answers FROM leaderboard WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            print(f"[Database] Rank Query Warning: User {user_id} not found in leaderboard.")
            return None  # User existiert nicht in DB
        score = row[0]

        # Rang berechnen: alle User zählen, die mehr Punkte haben
        cursor = await db.execute(
            "SELECT COUNT(*) FROM leaderboard WHERE correct_answers > ?",
            (score,)
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
            "SELECT correct_answers FROM leaderboard WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None, None
        score = row[0]

        # Nächsthöheren Score + User-ID finden
        cursor = await db.execute(
            "SELECT user_id, correct_answers FROM leaderboard WHERE correct_answers > ? ORDER BY correct_answers ASC LIMIT 1",
            (score,)
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
    Returns: (quest_date, quizzes_completed, voted_today, quest_completed, streak_freezes, bonus_hints)
    """
    today = datetime.date.today()
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT quest_date, quizzes_completed, voted_today, quest_completed, streak_freezes, bonus_hints FROM daily_quests WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            # Initialize new quest entry for today
            await db.execute(
                "INSERT INTO daily_quests (user_id, quest_date, quizzes_completed, voted_today, quest_completed, streak_freezes, bonus_hints) VALUES (?, ?, 0, 0, 0, 0, 0)",
                (user_id, today)
            )
            await db.commit()
            return (today, 0, 0, 0, 0, 0)
        
        quest_date_str, quizzes, voted, completed, freezes, hints = row
        quest_date = datetime.datetime.strptime(quest_date_str, "%Y-%m-%d").date()
        
        # Check if quest is from a previous day - reset if so
        if quest_date < today:
            await db.execute(
                "UPDATE daily_quests SET quest_date = ?, quizzes_completed = 0, voted_today = 0, quest_completed = 0 WHERE user_id = ?",
                (today, user_id)
            )
            await db.commit()
            return (today, 0, 0, 0, freezes, hints)
        
        return (quest_date, quizzes, voted, completed, freezes, hints)

async def increment_quest_quiz_count(user_id: int):
    """
    Increment the quiz count for today's quest.
    Returns True if quest was completed with this quiz.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Get current progress
        progress = await get_daily_quest_progress(user_id)
        _, quizzes, voted, completed, freezes, hints = progress
        
        # Don't increment if already at 5 or more
        if quizzes >= 5:
            return False
        
        new_count = quizzes + 1
        
        # Check if quest is now complete (only requires 5 quizzes)
        quest_complete = (new_count >= 5 and completed == 0)
        
        if quest_complete:
            # Quest completed! Award rewards
            await db.execute(
                "UPDATE daily_quests SET quizzes_completed = ?, quest_completed = 1, streak_freezes = streak_freezes + 1, bonus_hints = bonus_hints + 1 WHERE user_id = ?",
                (new_count, user_id)
            )
        else:
            await db.execute(
                "UPDATE daily_quests SET quizzes_completed = ? WHERE user_id = ?",
                (new_count, user_id)
            )
        
        await db.commit()
        return quest_complete

async def mark_quest_voted(user_id: int):
    """
    Mark that the user has voted today.
    Returns True if quest was completed with this vote.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Get current progress
        progress = await get_daily_quest_progress(user_id)
        _, quizzes, voted, completed, freezes, hints = progress
        
        # Don't mark if already voted
        if voted == 1:
            return False
        
        # Check if quest is now complete
        quest_complete = (quizzes >= 5 and completed == 0)
        
        if quest_complete:
            # Quest completed! Award rewards
            await db.execute(
                "UPDATE daily_quests SET voted_today = 1, quest_completed = 1, streak_freezes = streak_freezes + 1, bonus_hints = bonus_hints + 1 WHERE user_id = ?",
                (user_id,)
            )
        else:
            await db.execute(
                "UPDATE daily_quests SET voted_today = 1 WHERE user_id = ?",
                (user_id,)
            )
        
        await db.commit()
        return quest_complete

async def use_streak_freeze(user_id: int):
    """
    Use a streak freeze to prevent streak reset.
    Returns True if freeze was available and used.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT streak_freezes FROM daily_quests WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row or row[0] <= 0:
            return False
        
        # Use one freeze
        await db.execute(
            "UPDATE daily_quests SET streak_freezes = streak_freezes - 1 WHERE user_id = ?",
            (user_id,)
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
            "SELECT bonus_hints FROM daily_quests WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row or row[0] <= 0:
            return False
        
        # Use one hint
        await db.execute(
            "UPDATE daily_quests SET bonus_hints = bonus_hints - 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()
        return True

async def get_quest_rewards(user_id: int):
    """
    Get the current number of streak freezes and bonus hints.
    Returns: (streak_freezes, bonus_hints)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT streak_freezes, bonus_hints FROM daily_quests WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return (0, 0)
        
        return row

