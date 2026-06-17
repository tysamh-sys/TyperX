import os
import sqlite3
import json

class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_dir = os.path.join(base_dir, "data")
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)
            self.db_path = os.path.join(db_dir, "typing_game.db")
        else:
            self.db_path = db_path
            
        self.conn = None
        self._init_db()

    def _get_connection(self):
        # Establish connection with autocommit or thread-safety if needed,
        # but standard connection is fine for simple pygame loop.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create profiles table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 0,
            last_difficulty TEXT DEFAULT 'medium'
        )
        """)
        
        # Create stats table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            profile_id INTEGER NOT NULL,
            difficulty TEXT NOT NULL,
            mode TEXT NOT NULL,
            current_level INTEGER DEFAULT 1,
            highest_score INTEGER DEFAULT 0,
            total_games INTEGER DEFAULT 0,
            total_words INTEGER DEFAULT 0,
            correct_keystrokes INTEGER DEFAULT 0,
            total_keystrokes INTEGER DEFAULT 0,
            longest_combo INTEGER DEFAULT 0,
            play_time REAL DEFAULT 0.0,
            PRIMARY KEY (profile_id, difficulty, mode),
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        """)
        
        # Create custom_text table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_text (
            profile_id INTEGER PRIMARY KEY,
            raw_text TEXT DEFAULT '',
            words_json TEXT DEFAULT '[]',
            sentences_json TEXT DEFAULT '[]',
            use_custom INTEGER DEFAULT 0,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
        )
        """)
        
        conn.commit()
        conn.close()
        
        # Verify if any active profile exists. If not, auto-create a default
        self._ensure_default_profile()

    def _ensure_default_profile(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM profiles")
        row = cursor.fetchone()
        if row["cnt"] == 0:
            # Create default profile "Operator"
            cursor.execute("INSERT INTO profiles (name, is_active) VALUES ('Operator', 1)")
            prof_id = cursor.lastrowid
            
            # Initialize stats rows for all modes and all 3 difficulties
            for diff in ["beginner", "medium", "hard"]:
                for mode in ["survival", "reflex", "precision"]:
                    cursor.execute("""
                    INSERT INTO stats (profile_id, difficulty, mode)
                    VALUES (?, ?, ?)
                    """, (prof_id, diff, mode))
            
            # Initialize custom text row
            cursor.execute("""
            INSERT INTO custom_text (profile_id) VALUES (?)
            """, (prof_id,))
            
            conn.commit()
        conn.close()
        
        # Ensure existing profiles have precision rows (migration)
        self._migrate_precision_mode()

    def _migrate_precision_mode(self):
        """Ensures all existing profiles have precision stats rows (idempotent)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM profiles")
        profile_ids = [r["id"] for r in cursor.fetchall()]
        for prof_id in profile_ids:
            for diff in ["beginner", "medium", "hard"]:
                cursor.execute("""
                INSERT OR IGNORE INTO stats (profile_id, difficulty, mode)
                VALUES (?, ?, 'precision')
                """, (prof_id, diff))
        conn.commit()
        conn.close()

    # ---- Profile Methods ----

    def create_profile(self, name):
        name = name.strip()
        if not name:
            return False, "Profile name cannot be empty."
        
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Set all other profiles inactive first
            cursor.execute("UPDATE profiles SET is_active = 0")
            
            # Insert new profile as active
            cursor.execute("INSERT INTO profiles (name, is_active) VALUES (?, 1)", (name,))
            prof_id = cursor.lastrowid
            
            # Create initial stats and custom text
            for diff in ["beginner", "medium", "hard"]:
                for mode in ["survival", "reflex", "precision"]:
                    cursor.execute("""
                    INSERT INTO stats (profile_id, difficulty, mode)
                    VALUES (?, ?, ?)
                    """, (prof_id, diff, mode))
                    
            cursor.execute("INSERT INTO custom_text (profile_id) VALUES (?)", (prof_id,))
            
            conn.commit()
            return True, prof_id
        except sqlite3.IntegrityError:
            conn.rollback()
            return False, f"Profile name '{name}' already exists."
        finally:
            conn.close()

    def select_profile(self, profile_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE profiles SET is_active = 0")
        cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (profile_id,))
        conn.commit()
        conn.close()

    def delete_profile(self, profile_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if this profile is active
        cursor.execute("SELECT is_active FROM profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        was_active = row and row["is_active"] == 1
        
        # Delete profile (Cascade deletes stats & custom_text)
        # Note: SQLite needs PRAGMA foreign_keys = ON; for cascade delete, or we can delete manually.
        # Let's delete manually to be safe and cross-database compatible.
        cursor.execute("DELETE FROM stats WHERE profile_id = ?", (profile_id,))
        cursor.execute("DELETE FROM custom_text WHERE profile_id = ?", (profile_id,))
        cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        
        # If it was active, select another profile as active
        if was_active:
            cursor.execute("SELECT id FROM profiles LIMIT 1")
            next_row = cursor.fetchone()
            if next_row:
                cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (next_row["id"],))
                
        conn.commit()
        conn.close()
        
        # Ensure we always have at least one profile
        self._ensure_default_profile()

    def get_profiles(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles ORDER BY name")
        rows = cursor.fetchall()
        profiles = [dict(r) for r in rows]
        conn.close()
        return profiles

    def get_active_profile(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        profile = dict(row) if row else None
        conn.close()
        return profile

    def set_last_difficulty(self, profile_id, difficulty):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE profiles SET last_difficulty = ? WHERE id = ?", (difficulty, profile_id))
        conn.commit()
        conn.close()

    # ---- Stats Methods ----

    def get_stats(self, profile_id, difficulty, mode):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM stats WHERE profile_id = ? AND difficulty = ? AND mode = ?
        """, (profile_id, difficulty, mode))
        row = cursor.fetchone()
        stats = dict(row) if row else None
        conn.close()
        return stats

    def get_all_stats_for_profile(self, profile_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stats WHERE profile_id = ?", (profile_id,))
        rows = cursor.fetchall()
        stats_list = [dict(r) for r in rows]
        conn.close()
        return stats_list

    def save_game_session(self, profile_id, difficulty, mode, level, score, words, correct, total, combo, elapsed_time):
        """Update database stats using the metrics from a single completed game session."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get existing stats
        cursor.execute("""
        SELECT * FROM stats WHERE profile_id = ? AND difficulty = ? AND mode = ?
        """, (profile_id, difficulty, mode))
        row = cursor.fetchone()
        
        if row:
            new_level = max(row["current_level"], level)
            new_high_score = max(row["highest_score"], score)
            new_total_games = row["total_games"] + 1
            new_total_words = row["total_words"] + words
            new_correct = row["correct_keystrokes"] + correct
            new_total_keys = row["total_keystrokes"] + total
            new_longest_combo = max(row["longest_combo"], combo)
            new_play_time = row["play_time"] + elapsed_time
            
            cursor.execute("""
            UPDATE stats SET 
                current_level = ?, highest_score = ?, total_games = ?, total_words = ?,
                correct_keystrokes = ?, total_keystrokes = ?, longest_combo = ?, play_time = ?
            WHERE profile_id = ? AND difficulty = ? AND mode = ?
            """, (new_level, new_high_score, new_total_games, new_total_words,
                  new_correct, new_total_keys, new_longest_combo, new_play_time,
                  profile_id, difficulty, mode))
        else:
            # Fallback insertion (should not happen since we initialize rows)
            cursor.execute("""
            INSERT INTO stats (profile_id, difficulty, mode, current_level, highest_score, total_games, total_words, correct_keystrokes, total_keystrokes, longest_combo, play_time)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """, (profile_id, difficulty, mode, level, score, words, correct, total, combo, elapsed_time))
            
        conn.commit()
        conn.close()

    def reset_profile_stats(self, profile_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE stats SET 
            current_level = 1, highest_score = 0, total_games = 0, total_words = 0,
            correct_keystrokes = 0, total_keystrokes = 0, longest_combo = 0, play_time = 0.0
        WHERE profile_id = ?
        """, (profile_id,))
        conn.commit()
        conn.close()

    # ---- Custom Text Methods ----

    def get_custom_text(self, profile_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_text WHERE profile_id = ?", (profile_id,))
        row = cursor.fetchone()
        custom_data = dict(row) if row else None
        conn.close()
        return custom_data

    def save_custom_text(self, profile_id, raw_text, words, sentences, use_custom):
        conn = self._get_connection()
        cursor = conn.cursor()
        words_str = json.dumps(words)
        sentences_str = json.dumps(sentences)
        
        cursor.execute("""
        INSERT OR REPLACE INTO custom_text (profile_id, raw_text, words_json, sentences_json, use_custom)
        VALUES (?, ?, ?, ?, ?)
        """, (profile_id, raw_text, words_str, sentences_str, int(use_custom)))
        
        conn.commit()
        conn.close()

    def set_use_custom_text(self, profile_id, use_custom):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE custom_text SET use_custom = ? WHERE profile_id = ?
        """, (int(use_custom), profile_id))
        conn.commit()
        conn.close()
