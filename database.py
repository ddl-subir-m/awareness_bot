import sqlite3
import uuid
from datetime import datetime, timedelta
import json
import logging
from threading import Lock
from typing import Dict, Optional, List, Any

logger = logging.getLogger('nervous_system_coach')

class DatabaseManager:
    def __init__(self, db_path="nervous_system_coach.db"):
        self.db_path = db_path
        self.lock = Lock()
        self.logger = logging.getLogger('nervous_system_coach.db')
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

                # Memory Summaries table
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
                
                # Add new tables for enhanced context management
                
                # User Insights table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    category TEXT,
                    content TEXT,
                    confidence FLOAT,
                    source_message_ids TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_validated DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)
                
                # Topics table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    name TEXT,
                    relevance_score FLOAT,
                    first_mentioned DATETIME,
                    last_mentioned DATETIME,
                    mention_count INTEGER DEFAULT 1,
                    is_resolved BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)
                
                # Progress Metrics table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS progress_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    metric_name TEXT,
                    value FLOAT,
                    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)
                
                # Action Items table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    content TEXT,
                    source_message_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    completed_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (source_message_id) REFERENCES conversations (id)
                )
                """)
                
                # Message Analysis table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    user_id TEXT,
                    intent TEXT,
                    emotional_state TEXT,
                    urgency_level INTEGER,
                    topics TEXT,
                    potential_triggers TEXT,
                    FOREIGN KEY (message_id) REFERENCES conversations (id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)
                
                # Session tracking table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    start_time DATETIME,
                    end_time DATETIME,
                    message_count INTEGER DEFAULT 0,
                    summary TEXT,
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

    def save_conversation(self, user_id: str, role: str, content: str) -> int:
        """Save a conversation message if it doesn't already exist"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Enhanced duplicate detection - check content similarity and timing
                cursor.execute("""
                SELECT id, content 
                FROM conversations 
                WHERE user_id = ? 
                AND role = ? 
                AND timestamp >= datetime('now', '-1 minute')
                ORDER BY timestamp DESC
                LIMIT 5
                """, (user_id, role))
                
                recent_messages = cursor.fetchall()
                
                # Check for exact or near duplicates
                for msg_id, msg_content in recent_messages:
                    if (
                        content == msg_content or  # Exact match
                        (len(content) > 10 and content in msg_content) or  # Substring match for longer messages
                        (len(msg_content) > 10 and msg_content in content)  # Reverse substring match
                    ):
                        return msg_id  # Return existing message ID
                
                # Insert new message if no duplicate found
                cursor.execute("""
                INSERT INTO conversations (user_id, role, content, timestamp)
                VALUES (?, ?, ?, datetime('now'))
                """, (user_id, role, content))
                
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_conversation_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a user with proper timestamp handling"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT role, content, timestamp
                    FROM conversations
                    WHERE user_id = ?
                    ORDER BY timestamp ASC
                """, (user_id,))
                
                results = cursor.fetchall()
                return [{
                    "role": row[0],
                    "content": row[1],
                    "timestamp": row[2] if row[2] else datetime.now().isoformat()
                } for row in results]
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
        """Get conversations for a specific timeframe with improved date handling"""
        # Get current time for consistency across the method
        current_time = datetime.now()
        
        # Define timeframes clearly using date-only comparison
        if timeframe == "daily":
            # Get conversations from the previous day
            start_time = (current_time - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            logger.info(f"Getting daily conversations from {start_time} to {end_time}")
        elif timeframe == "weekly":
            # Get conversations from the past 7 days
            start_time = (current_time - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
            logger.info(f"Getting weekly conversations from {start_time} to {end_time}")
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        # Format for SQLite
        start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT role, content, timestamp
                    FROM conversations
                    WHERE user_id = ? 
                    AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                """, (user_id, start_time_str, end_time_str))
                
                results = cursor.fetchall()
                logger.info(f"Found {len(results)} conversations for {timeframe} timeframe")
                
                if results:
                    timestamps = [row[2] for row in results]
                    logger.debug(f"Conversation timestamps: {timestamps[:3]}{'...' if len(timestamps) > 3 else ''}")
                
                return [{"role": role, "content": content} for role, content, _ in results if role and content]
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

    def save_user_insight(self, user_id: str, category: str, content: str, 
                        confidence: float, source_message_ids: List[int]) -> int:
        """Save a new insight about the user"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO user_insights (
                    user_id, category, content, confidence, source_message_ids, created_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'))
                """, (
                    user_id, category, content, confidence, 
                    json.dumps(source_message_ids)
                ))
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()
    
    def get_user_insights(self, user_id: str, categories: Optional[List[str]] = None, 
                         min_confidence: float = 0.5) -> List[Dict[str, Any]]:
        """Get insights about a user, optionally filtered by category and confidence"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                query = """
                SELECT id, category, content, confidence, created_at, last_validated
                FROM user_insights
                WHERE user_id = ? AND confidence >= ?
                """
                params = [user_id, min_confidence]
                
                if categories:
                    placeholders = ', '.join('?' for _ in categories)
                    query += f" AND category IN ({placeholders})"
                    params.extend(categories)
                
                query += " ORDER BY confidence DESC, created_at DESC"
                
                cursor.execute(query, params)
                
                results = cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "category": row[1],
                        "content": row[2],
                        "confidence": row[3],
                        "created_at": row[4],
                        "last_validated": row[5]
                    }
                    for row in results
                ]
            finally:
                conn.close()
    
    def update_or_create_topic(self, user_id: str, topic_name: str, 
                              relevance_score: float) -> int:
        """Update an existing topic or create a new one with deduplication"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Normalize topic name for comparison
                normalized_name = topic_name.lower().strip()
                
                # Check for similar topics
                cursor.execute("""
                SELECT id, name, mention_count, relevance_score
                FROM topics
                WHERE user_id = ? AND LOWER(name) = ?
                """, (user_id, normalized_name))
                
                result = cursor.fetchone()
                
                if result:
                    # Update existing topic
                    topic_id, name, mention_count, old_relevance = result
                    new_mention_count = mention_count + 1
                    
                    # Calculate new relevance score as weighted average
                    new_relevance = (old_relevance * mention_count + relevance_score) / new_mention_count
                    
                    cursor.execute("""
                    UPDATE topics
                    SET mention_count = ?, 
                        relevance_score = ?, 
                        last_mentioned = datetime('now'),
                        name = CASE 
                            WHEN LENGTH(?) > LENGTH(name) THEN ?
                            ELSE name
                        END
                    WHERE id = ?
                    """, (new_mention_count, new_relevance, topic_name, topic_name, topic_id))
                    
                    conn.commit()
                    return topic_id
                else:
                    # Create new topic
                    cursor.execute("""
                    INSERT INTO topics (
                        user_id, name, relevance_score, first_mentioned, last_mentioned
                    ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                    """, (user_id, topic_name, relevance_score))
                    
                    conn.commit()
                    return cursor.lastrowid
            finally:
                conn.close()
    
    def get_active_topics(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most active topics for a user"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Get topics mentioned in the last 7 days or with highest mention count
                cursor.execute("""
                SELECT name, relevance_score, first_mentioned, last_mentioned, mention_count, is_resolved
                FROM topics
                WHERE user_id = ? AND (
                    last_mentioned >= datetime('now', '-7 days') OR
                    mention_count >= 3
                )
                ORDER BY relevance_score * mention_count DESC, last_mentioned DESC
                LIMIT ?
                """, (user_id, limit))
                
                results = cursor.fetchall()
                return [
                    {
                        "name": row[0],
                        "relevance": row[1],
                        "first_mentioned": row[2],
                        "last_mentioned": row[3],
                        "mention_count": row[4],
                        "is_resolved": bool(row[5])
                    }
                    for row in results
                ]
            finally:
                conn.close()
    
    def save_message_analysis(self, message_id: int, user_id: str, 
                             analysis: Dict[str, Any]) -> int:
        """Save analysis of a user message"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Extract fields from analysis dict
                intent = analysis.get('primary_intent', '')
                emotional_state = analysis.get('emotional_state', '')
                urgency_level = analysis.get('urgency_level', 5)
                topics = json.dumps(analysis.get('topics', []))
                potential_triggers = analysis.get('potential_triggers', '')
                
                cursor.execute("""
                INSERT INTO message_analysis (
                    message_id, user_id, intent, emotional_state, urgency_level, topics, potential_triggers
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_id, user_id, intent, emotional_state, 
                    urgency_level, topics, potential_triggers
                ))
                
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()
    
    def get_message_analysis(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent message analyses for a user"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                SELECT ma.id, c.content as message_content, ma.intent, ma.emotional_state, 
                       ma.urgency_level, ma.topics, ma.potential_triggers, c.timestamp
                FROM message_analysis ma
                JOIN conversations c ON ma.message_id = c.id
                WHERE ma.user_id = ? AND c.role = 'user'
                ORDER BY c.timestamp DESC
                LIMIT ?
                """, (user_id, limit))
                
                results = cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "message_content": row[1],
                        "intent": row[2],
                        "emotional_state": row[3],
                        "urgency_level": row[4],
                        "topics": json.loads(row[5]),
                        "potential_triggers": row[6],
                        "timestamp": row[7]
                    }
                    for row in results
                ]
            finally:
                conn.close()
    
    def save_action_item(self, user_id: str, content: str, 
                        source_message_id: int) -> int:
        """Save a new action item"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO action_items (
                    user_id, content, source_message_id
                ) VALUES (?, ?, ?)
                """, (user_id, content, source_message_id))
                
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()
    
    def get_pending_action_items(self, user_id: str) -> List[Dict[str, Any]]:
        """Get pending action items for a user"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                SELECT id, content, created_at
                FROM action_items
                WHERE user_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                """, (user_id,))
                
                results = cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "content": row[1],
                        "created_at": row[2]
                    }
                    for row in results
                ]
            finally:
                conn.close()
    
    def update_action_item_status(self, item_id: int, status: str, 
                                completed_at: Optional[str] = None) -> bool:
        """Update an action item's status"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                if completed_at:
                    cursor.execute("""
                    UPDATE action_items
                    SET status = ?, completed_at = ?
                    WHERE id = ?
                    """, (status, completed_at, item_id))
                else:
                    cursor.execute("""
                    UPDATE action_items
                    SET status = ?
                    WHERE id = ?
                    """, (status, item_id))
                
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()
    
    def save_progress_metric(self, user_id: str, metric_name: str, 
                           value: float, notes: Optional[str] = None) -> int:
        """Save a progress metric value"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO progress_metrics (
                    user_id, metric_name, value, notes
                ) VALUES (?, ?, ?, ?)
                """, (user_id, metric_name, value, notes))
                
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()
    
    def get_metric_history(self, user_id: str, metric_name: str, 
                         days: int = 30) -> List[Dict[str, Any]]:
        """Get historical values for a specific metric"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute("""
                SELECT value, recorded_at, notes
                FROM progress_metrics
                WHERE user_id = ? AND metric_name = ? AND recorded_at >= datetime('now', '-' || ? || ' days')
                ORDER BY recorded_at ASC
                """, (user_id, metric_name, days))
                
                results = cursor.fetchall()
                return [
                    {
                        "value": row[0],
                        "recorded_at": row[1],
                        "notes": row[2]
                    }
                    for row in results
                ]
            finally:
                conn.close()
    
    def get_current_session_id(self, user_id: str) -> Optional[int]:
        """Get the current session ID or create a new one if needed"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Check for an active session (less than 30 minutes old)
                cursor.execute("""
                SELECT id, start_time
                FROM sessions
                WHERE user_id = ? AND end_time IS NULL
                ORDER BY start_time DESC
                LIMIT 1
                """, (user_id,))
                
                result = cursor.fetchone()
                current_time = datetime.now()
                
                if result:
                    session_id, start_time = result
                    start_time = datetime.fromisoformat(start_time)
                    
                    # Check if session is still active (less than 30 minutes since last activity)
                    cursor.execute("""
                    SELECT MAX(timestamp) 
                    FROM conversations 
                    WHERE user_id = ?
                    """, (user_id,))
                    
                    last_message_time = cursor.fetchone()[0]
                    
                    if last_message_time:
                        last_message_time = datetime.fromisoformat(last_message_time)
                        time_diff = (current_time - last_message_time).total_seconds() / 60
                        
                        if time_diff <= 30:  # Session still active
                            return session_id
                
                # Create a new session
                cursor.execute("""
                INSERT INTO sessions (
                    user_id, start_time
                ) VALUES (?, ?)
                """, (user_id, current_time.isoformat()))
                
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()
    
    def end_session(self, session_id: int, summary: Optional[str] = None) -> bool:
        """End a session and optionally add a summary"""
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Update message count
                cursor.execute("""
                SELECT user_id FROM sessions WHERE id = ?
                """, (session_id,))
                result = cursor.fetchone()
                
                if not result:
                    return False
                    
                user_id = result[0]
                
                # Count messages in this session
                cursor.execute("""
                SELECT COUNT(*) FROM conversations
                WHERE user_id = ? AND timestamp >= (SELECT start_time FROM sessions WHERE id = ?)
                """, (user_id, session_id))
                
                message_count = cursor.fetchone()[0]
                
                # End the session
                end_time = datetime.now().isoformat()
                cursor.execute("""
                UPDATE sessions
                SET end_time = ?, message_count = ?, summary = ?
                WHERE id = ?
                """, (end_time, message_count, summary, session_id))
                
                conn.commit()
                return True
            finally:
                conn.close()



    def get_insights_for_timeframe(self, user_id: str, timeframe: str) -> List[Dict[str, Any]]:
        """
        Get insights created within a specific timeframe
        
        Args:
            user_id: The user's ID
            timeframe: 'daily' or 'weekly'
            
        Returns:
            List of insights from this timeframe
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Calculate the start time based on timeframe
                if timeframe == "daily":
                    time_ago = "1 day"
                elif timeframe == "weekly":
                    time_ago = "7 days"
                else:
                    raise ValueError(f"Unsupported timeframe: {timeframe}")
                
                cursor.execute("""
                SELECT id, category, content, confidence, created_at
                FROM user_insights
                WHERE user_id = ? 
                AND created_at >= datetime('now', '-' || ?)
                ORDER BY confidence DESC, created_at DESC
                """, (user_id, time_ago))
                
                results = cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "category": row[1],
                        "content": row[2],
                        "confidence": row[3],
                        "created_at": row[4]
                    }
                    for row in results
                ]
            finally:
                conn.close()

    def get_action_items_for_timeframe(self, user_id: str, timeframe: str) -> List[Dict[str, Any]]:
        """
        Get action items created within a specific timeframe
        
        Args:
            user_id: The user's ID
            timeframe: 'daily' or 'weekly'
            
        Returns:
            List of action items from this timeframe
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Calculate the start time based on timeframe
                if timeframe == "daily":
                    time_ago = "1 day"
                elif timeframe == "weekly":
                    time_ago = "7 days"
                else:
                    raise ValueError(f"Unsupported timeframe: {timeframe}")
                
                cursor.execute("""
                SELECT id, content, created_at, status
                FROM action_items
                WHERE user_id = ? 
                AND created_at >= datetime('now', '-' || ?)
                ORDER BY created_at DESC
                """, (user_id, time_ago))
                
                results = cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "content": row[1],
                        "created_at": row[2],
                        "status": row[3]
                    }
                    for row in results
                ]
            finally:
                conn.close()

    def get_emotional_metrics_for_timeframe(self, user_id: str, timeframe: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get emotional metrics recorded within a specific timeframe
        
        Args:
            user_id: The user's ID
            timeframe: 'daily' or 'weekly'
            
        Returns:
            Dictionary of metric names to lists of metric values
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Calculate the start time based on timeframe
                if timeframe == "daily":
                    time_ago = "1 day"
                elif timeframe == "weekly":
                    time_ago = "7 days"
                else:
                    raise ValueError(f"Unsupported timeframe: {timeframe}")
                
                # Get all metrics from the last day/week
                cursor.execute("""
                SELECT metric_name, value, recorded_at, notes
                FROM progress_metrics
                WHERE user_id = ? 
                AND recorded_at >= datetime('now', '-' || ?)
                ORDER BY recorded_at ASC
                """, (user_id, time_ago))
                
                results = cursor.fetchall()
                
                # Group by metric name
                metrics = {}
                for row in results:
                    metric_name = row[0]
                    if metric_name not in metrics:
                        metrics[metric_name] = []
                    
                    metrics[metric_name].append({
                        "value": row[1],
                        "recorded_at": row[2],
                        "notes": row[3]
                    })
                
                return metrics
            finally:
                conn.close()

    def get_topics_for_timeframe(self, user_id: str, timeframe: str) -> List[Dict[str, Any]]:
        """
        Get topics that were active within a specific timeframe
        
        Args:
            user_id: The user's ID
            timeframe: 'daily' or 'weekly'
            
        Returns:
            List of topics active in this timeframe
        """
        with self.lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Calculate the start time based on timeframe
                if timeframe == "daily":
                    time_ago = "1 day"
                elif timeframe == "weekly":
                    time_ago = "7 days"
                else:
                    raise ValueError(f"Unsupported timeframe: {timeframe}")
                
                cursor.execute("""
                SELECT name, relevance_score, first_mentioned, last_mentioned, mention_count
                FROM topics
                WHERE user_id = ? 
                AND last_mentioned >= datetime('now', '-' || ?)
                ORDER BY relevance_score * mention_count DESC
                """, (user_id, time_ago))
                
                results = cursor.fetchall()
                return [
                    {
                        "name": row[0],
                        "relevance": row[1],
                        "first_mentioned": row[2],
                        "last_mentioned": row[3],
                        "mention_count": row[4]
                    }
                    for row in results
                ]
            finally:
                conn.close()