import logging
import time
from datetime import datetime, timedelta
import threading
from typing import Dict, Any, List, Optional

class SummaryScheduler:
    """
    Scheduler for generating summaries on a regular basis.
    This runs in a separate thread to avoid blocking the main Streamlit application.
    """
    
    def __init__(self, api_key: str, db_manager, memory_processor=None):
        self.api_key = api_key
        self.db = db_manager
        self.memory_processor = memory_processor
        self.logger = logging.getLogger('nervous_system_coach.summary_scheduler')
        self.running = False
        self.thread = None
        self.last_check = {}  # Track last check time for each user
    
    def start(self):
        """Start the scheduler in a new thread"""
        if self.thread and self.thread.is_alive():
            self.logger.info("Scheduler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler)
        self.thread.daemon = True  # Thread will exit when main thread exits
        self.thread.start()
        self.logger.info("Summary scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.logger.info("Summary scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        self.logger.info("Scheduler running")
        while self.running:
            try:
                self._check_all_users()
            except Exception as e:
                self.logger.error(f"Error in scheduler: {e}")
            
            # Sleep for 15 minutes before checking again
            # In a production app, this would be more sophisticated
            time.sleep(15 * 60)
    
    def _check_all_users(self):
        """Check all users for summary generation needs"""
        # Get all user IDs from the database
        users = self._get_all_user_ids()
        self.logger.info(f"Checking {len(users)} users for summary needs")
        
        for user_id in users:
            # Only check each user once per hour to avoid excessive processing
            last_check_time = self.last_check.get(user_id)
            if last_check_time and (datetime.now() - last_check_time).total_seconds() < 3600:
                continue
            
            try:
                # Generate summaries if needed
                if self.memory_processor:
                    self.memory_processor.generate_summaries(user_id)
                else:
                    self.logger.warning(f"No memory processor available for user {user_id}")
                self.last_check[user_id] = datetime.now()
            except Exception as e:
                self.logger.error(f"Error generating summaries for user {user_id}: {e}")
    
    def _get_all_user_ids(self) -> List[str]:
        """Get all user IDs from the database"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def generate_now(self, user_id: str, timeframe: str) -> bool:
        """
        Generate a summary immediately for a specific user and timeframe
        
        Args:
            user_id: The user's ID
            timeframe: 'daily' or 'weekly'
        """
        if not self.memory_processor:
            self.logger.error("No memory processor available for generating summaries")
            return False
            
        try:
            self.memory_processor.generate_timeframe_summary(user_id, timeframe)
            return True
        except Exception as e:
            self.logger.error(f"Error generating {timeframe} summary for user {user_id}: {e}")
            return False