import sqlite3
import logging

DB_FILE = "bot_data.db"
logger = logging.getLogger("dittologger")

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # posted articles
    cursor.execute('''CREATE TABLE IF NOT EXISTS posted_articles (
                        link TEXT PRIMARY KEY)''')

    # PTCG channels & roles
    cursor.execute('''CREATE TABLE IF NOT EXISTS ptcg_channels (
                        server_id TEXT PRIMARY KEY, 
                        channel_id TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ptcg_roles (
                        server_id TEXT PRIMARY KEY, 
                        role_id TEXT)''')
    
    # Pocket channels & roles
    cursor.execute('''CREATE TABLE IF NOT EXISTS pocket_channels (
                        server_id TEXT PRIMARY KEY, 
                        channel_id TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pocket_roles (
                        server_id TEXT PRIMARY KEY, 
                        role_id TEXT)''')
    
    # regex patterns
    cursor.execute('''CREATE TABLE IF NOT EXISTS regex_patterns (
                        server_id TEXT PRIMARY KEY,
                        pattern TEXT)''')
    
    # regex-ignored channels
    cursor.execute('''CREATE TABLE IF NOT EXISTS regex_ignored_channels (
                    server_id TEXT,
                    channel_id TEXT,
                    PRIMARY KEY (server_id, channel_id))''')
    
    conn.commit()
    conn.close()

    logger.info(f"Database successfully set up!")

# SQLite functions
# SAVES articles to prevent future repeating articles
def save_posted_article(link):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO posted_articles (link) VALUES (?)", (link,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save article: {e}")
    finally:
        conn.close()

# LOADS previously posted articles to avoid repeats
def load_posted_articles():
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT link FROM posted_articles")
        links = {row[0] for row in cursor.fetchall()}
        return links
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to load articles: {e}")
        return set()
    finally:
        conn.close()

# SAVES the posting channel for PTCG articles
def save_ptcg_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ptcg_channels (server_id, channel_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET channel_id = excluded.channel_id", 
                    (server_id, channel_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save ptcg channel: {e}")
    finally:
        conn.close()

# GETS the posting channel for PTCG articles
def get_ptcg_channel(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id FROM ptcg_channels WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get ptcg channel: {e}")
        return None
    finally:
        conn.close()

def get_all_ptcg_channels():
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT server_id, channel_id FROM ptcg_channels")
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get all ptcg channels: {e}")
        return []
    finally:
        conn.close()

# SAVES the ping role for PTCG articles
def save_ptcg_role(server_id, role_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ptcg_roles (server_id, role_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET role_id = excluded.role_id", 
                    (server_id, role_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save ptcg role: {e}")
    finally:
        conn.close()

# GETS the ping role for PTCG articles
def get_ptcg_role(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role_id FROM ptcg_roles WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get ptcg role: {e}")
        return None
    finally:
        conn.close()

# SAVES the posting channel for Pocket articles
def save_pocket_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pocket_channels (server_id, channel_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET channel_id = excluded.channel_id", 
                    (server_id, channel_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save pocket channel: {e}")
    finally:
        conn.close()

# GETS the posting channel for Pocket articles
def get_pocket_channel(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id FROM pocket_channels WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get pocket channel: {e}")
        return None
    finally:
        conn.close()

def get_all_pocket_channels():
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT server_id, channel_id FROM pocket_channels")
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get all pocket channels: {e}")
        return []
    finally:
        conn.close()

# SAVES the ping role for Pocket articles
def save_pocket_role(server_id, role_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pocket_roles (server_id, role_id) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET role_id = excluded.role_id", 
                    (server_id, role_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save pocket role: {e}")
    finally:
        conn.close()

# GETS the ping role for Pocket articles
def get_pocket_role(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role_id FROM pocket_roles WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get pocket role: {e}")
        return None
    finally:
        conn.close()

# SAVES regex pattern
def save_regex_pattern(server_id, pattern):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO regex_patterns (server_id, pattern) VALUES (?, ?) ON CONFLICT(server_id) DO UPDATE SET pattern = excluded.pattern", 
                    (server_id, pattern))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save regex pattern: {e}")
    finally:
        conn.close()

# GETS regex pattern
def get_regex_pattern(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT pattern FROM regex_patterns WHERE server_id = ?", (server_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get regex pattern: {e}")
        return None
    finally:
        conn.close()

# REMOVES regex pattern
def remove_regex_pattern(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM regex_patterns WHERE server_id = ?", (server_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to remove regex pattern: {e}")
    finally:
        conn.close()

# SAVES regex ignored channel
def save_regex_ignored_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO regex_ignored_channels (server_id, channel_id) VALUES (?, ?)",
            (server_id, channel_id),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to save regex ignored channel: {e}")
    finally:
        conn.close()

# REMOVES regex ignored channel
def remove_regex_ignored_channel(server_id, channel_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM regex_ignored_channels WHERE server_id = ? AND channel_id = ?",
            (server_id, channel_id),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to remove regex ignored channel: {e}")
    finally:
        conn.close()

# GETS regex ignored channel
def get_regex_ignored_channels(server_id):
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT channel_id FROM regex_ignored_channels WHERE server_id = ?", (server_id,)
        )
        ignored = {row[0] for row in cursor.fetchall()}
        return ignored
    except sqlite3.Error as e:
        logger.error(f"Database error while trying to get regex ignored channels: {e}")
        return set()
    finally:
        conn.close()
