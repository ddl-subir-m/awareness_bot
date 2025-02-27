import sqlite3
import uuid
from datetime import datetime
import json
from threading import Lock
from typing import Dict, Optional, List

class DatabaseManager:
    def __init__(self):
        self.db_path = "nervous_system_coach.db"
        self.lock = Lock()
        self._init_db()
    
    def get_connection(self):
        """Create a new connection for the current thread"""
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database with required tables"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Create users table if it doesn't exist
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    passphrase TEXT NOT NULL,
                    coach_name TEXT DEFAULT NULL,
                    coach_vibes TEXT DEFAULT NULL,
                    custom_instructions TEXT DEFAULT NULL,
                    codex_vitae TEXT DEFAULT '{}',
                    selected_model TEXT DEFAULT 'gpt-4o-mini',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Create conversation history table if it doesn't exist
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)

                # Add new Memory Summaries table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    timeframe TEXT,
                    summary JSON,
                    start_date DATETIME,
                    end_date DATETIME,
                    last_updated DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)

                conn.commit()
            finally:
                conn.close()

    def create_user(self, name, passphrase):
        """Create a new user"""
        user_id = str(uuid.uuid4())
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                # Insert new user with default values
                cursor.execute("""
                INSERT INTO users (
                    user_id, 
                    name, 
                    passphrase, 
                    coach_name,
                    coach_vibes,
                    custom_instructions,
                    codex_vitae,
                    selected_model
                ) VALUES (?, ?, ?, '', '', '', '{}', 'gpt-4o-mini')
                """, (user_id, name, passphrase))
                conn.commit()
                return user_id
            finally:
                conn.close()

    def authenticate_user(self, name, passphrase):
        """Authenticate user and return user_id if successful"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE name = ? AND passphrase = ?", 
                             (name, passphrase))
                result = cursor.fetchone()
                return result[0] if result else None
            finally:
                conn.close()

    def get_user_profile(self, user_id):
        """Get user profile information"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT 
                    user_id, 
                    name, 
                    coach_name, 
                    coach_vibes, 
                    custom_instructions, 
                    codex_vitae, 
                    selected_model 
                FROM users 
                WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                
                if result:
                    return {
                        'user_id': result[0],
                        'name': result[1],
                        'coach_name': result[2],
                        'coach_vibes': result[3],
                        'custom_instructions': result[4],
                        'codex_vitae': json.loads(result[5] if result[5] else "{}"),
                        'selected_model': result[6]
                    }
                # Return default profile if no result found
                return {
                    'user_id': user_id,
                    'name': '',
                    'coach_name': '',
                    'coach_vibes': '',
                    'custom_instructions': '',
                    'codex_vitae': {},
                    'selected_model': 'gpt-4o-mini'
                }
            finally:
                conn.close()

    def save_conversation(self, user_id, role, content):
        """Save a conversation message"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO conversations (user_id, role, content)
                VALUES (?, ?, ?)
                """, (user_id, role, content))
                conn.commit()
                # Debug print
                print(f"Saved message for user {user_id}: role={role}, content={content}")
            finally:
                conn.close()

    def get_conversation_history(self, user_id):
        """Get conversation history for a user"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                # Debug print
                print(f"Fetching conversation history for user {user_id}")
                
                cursor.execute("""
                SELECT role, content 
                FROM conversations 
                WHERE user_id = ? AND role IS NOT NULL AND content IS NOT NULL
                ORDER BY timestamp ASC
                """, (user_id,))
                
                results = cursor.fetchall()
                # Debug print
                print(f"Found {len(results)} messages in database")
                
                # Only return messages that have both role and content
                return [
                    {"role": role, "content": content} 
                    for role, content in results 
                    if role and content
                ]
            finally:
                conn.close()

    def update_codex_vitae(self, user_id, question_key, answer):
        """Update a specific entry in the codex vitae"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Get current codex_vitae
                cursor.execute("SELECT codex_vitae FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    codex_vitae = json.loads(result[0] if result[0] else "{}")
                    codex_vitae[question_key] = answer
                    
                    # Update the codex_vitae
                    cursor.execute("""
                    UPDATE users 
                    SET codex_vitae = ?
                    WHERE user_id = ?
                    """, (json.dumps(codex_vitae), user_id))
                    
                    conn.commit()
            finally:
                conn.close()

    def delete_codex_vitae_entry(self, user_id, question_key):
        """Delete a specific entry from the codex vitae"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Get current codex_vitae
                cursor.execute("SELECT codex_vitae FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    codex_vitae = json.loads(result[0] if result[0] else "{}")
                    if question_key in codex_vitae:
                        del codex_vitae[question_key]
                        
                        # Update the codex_vitae
                        cursor.execute("""
                        UPDATE users 
                        SET codex_vitae = ?
                        WHERE user_id = ?
                        """, (json.dumps(codex_vitae), user_id))
                        
                        conn.commit()
            finally:
                conn.close()

    def update_user_profile(self, user_id, name, coach_name, coach_vibes, custom_instructions, selected_model):
        """Update user profile information"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, name, passphrase, coach_name, coach_vibes, custom_instructions, codex_vitae, selected_model)
                SELECT 
                    ?, ?, passphrase, ?, ?, ?, codex_vitae, ?
                FROM users WHERE user_id = ?
                """, (user_id, name, coach_name, coach_vibes, custom_instructions, selected_model, user_id))
                
                if cursor.rowcount == 0:  # New user
                    cursor.execute("""
                    INSERT INTO users 
                    (user_id, name, coach_name, coach_vibes, custom_instructions, codex_vitae, selected_model)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, name, coach_name, coach_vibes, custom_instructions, "{}", selected_model))
                
                conn.commit()
            finally:
                conn.close()

def save_summary(self, user_id: str, timeframe: str, summary: Dict) -> None:
    """Save a new memory summary"""
    with self.lock:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO memory_summaries 
            (user_id, timeframe, summary, start_date, end_date, last_updated)
            VALUES (?, ?, ?, datetime('now', '-1 day'), datetime('now'), datetime('now'))
            """, (user_id, timeframe, json.dumps(summary)))
            conn.commit()
        finally:
            conn.close()

def get_latest_summary(self, user_id: str, timeframe: str) -> Optional[Dict]:
    """Get the most recent summary for a timeframe"""
    with self.lock:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT summary, last_updated
            FROM memory_summaries
            WHERE user_id = ? AND timeframe = ?
            ORDER BY last_updated DESC
            LIMIT 1
            """, (user_id, timeframe))
            result = cursor.fetchone()
            
            if result:
                return {
                    "summary": json.loads(result[0]),
                    "last_updated": result[1]
                }
            return None
        finally:
            conn.close()

def get_conversations_for_timeframe(self, user_id: str, timeframe: str) -> List[Dict]:
    """Get conversations for a specific timeframe"""
    timeframe_sql = {
        "daily": "datetime('now', '-1 day')",
        "weekly": "datetime('now', '-7 days')"
    }
    
    with self.lock:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
            SELECT role, content
            FROM conversations
            WHERE user_id = ? AND timestamp >= {timeframe_sql[timeframe]}
            ORDER BY timestamp ASC
            """, (user_id,))
            
            return [{"role": role, "content": content} for role, content in cursor.fetchall()]
        finally:
            conn.close()

def get_all_summaries(self, user_id: str) -> List[Dict]:
    """Get all summaries for a user"""
    with self.lock:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT timeframe, summary, start_date, end_date, last_updated
            FROM memory_summaries
            WHERE user_id = ?
            ORDER BY last_updated DESC
            """, (user_id,))
            
            results = cursor.fetchall()
            return [{
                "timeframe": result[0],
                "summary": json.loads(result[1]),
                "start_date": result[2],
                "end_date": result[3],
                "last_updated": result[4]
            } for result in results]
        finally:
            conn.close()
            
    def reset_database(self):
        """Reset the database by dropping and recreating tables"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                # Drop existing tables
                cursor.execute("DROP TABLE IF EXISTS conversations")
                cursor.execute("DROP TABLE IF EXISTS users")
                cursor.execute("DROP TABLE IF EXISTS memory_summaries")
                conn.commit()
                
                # Reinitialize database
                self._init_db()
            finally:
                conn.close()

    def save_summary(self, user_id: str, timeframe: str, summary: Dict) -> None:
        """Save a new memory summary"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO memory_summaries 
                (user_id, timeframe, summary, start_date, end_date, last_updated)
                VALUES (?, ?, ?, datetime('now', '-1 day'), datetime('now'), datetime('now'))
                """, (user_id, timeframe, json.dumps(summary)))
                conn.commit()
            finally:
                conn.close()

    def get_latest_summary(self, user_id: str, timeframe: str) -> Optional[Dict]:
        """Get the most recent summary for a timeframe"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT summary, last_updated
                FROM memory_summaries
                WHERE user_id = ? AND timeframe = ?
                ORDER BY last_updated DESC
                LIMIT 1
                """, (user_id, timeframe))
                result = cursor.fetchone()
                
                if result:
                    return {
                        "summary": json.loads(result[0]),
                        "last_updated": result[1]
                    }
                return None
            finally:
                conn.close()

    def get_conversations_for_timeframe(self, user_id: str, timeframe: str) -> List[Dict]:
        """Get conversations for a specific timeframe"""
        timeframe_sql = {
            "daily": "datetime('now', '-1 day')",
            "weekly": "datetime('now', '-7 days')"
        }
        
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(f"""
                SELECT role, content
                FROM conversations
                WHERE user_id = ? AND timestamp >= {timeframe_sql[timeframe]}
                ORDER BY timestamp ASC
                """, (user_id,))
                
                return [{"role": role, "content": content} for role, content in cursor.fetchall()]
            finally:
                conn.close()