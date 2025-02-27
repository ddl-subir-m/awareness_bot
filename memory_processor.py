import openai
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

class MemoryProcessor:
    def __init__(self, api_key: str, db_manager):
        self.api_key = api_key
        self.db = db_manager
        openai.api_key = api_key

    def process_conversation(self, user_id: str, conversation: Dict) -> None:
        """Process a new conversation and update memory summaries"""
        # Get existing summaries
        daily_summary = self.db.get_latest_summary(user_id, "daily")
        weekly_summary = self.db.get_latest_summary(user_id, "weekly")
        
        # Process daily summary
        if self._needs_new_summary(daily_summary, "daily"):
            self._generate_and_save_summary(user_id, "daily", conversation)
        
        # Process weekly summary
        if self._needs_new_summary(weekly_summary, "weekly"):
            self._generate_and_save_summary(user_id, "weekly", conversation)

    def _needs_new_summary(self, existing_summary: Optional[Dict], timeframe: str) -> bool:
        """Determine if a new summary needs to be generated"""
        if not existing_summary:
            return True
            
        last_update = datetime.fromisoformat(existing_summary.get("last_updated", "2000-01-01"))
        current_time = datetime.now()
        
        thresholds = {
            "daily": timedelta(hours=24),
            "weekly": timedelta(days=7)
        }
        
        return current_time - last_update > thresholds[timeframe]

    def _generate_and_save_summary(self, user_id: str, timeframe: str, conversation: Dict) -> None:
        """Generate and save a new summary"""
        # Get relevant conversations
        conversations = self.db.get_conversations_for_timeframe(user_id, timeframe)
        
        summary = self._generate_summary(conversations, timeframe)
        
        # Get existing summary to merge with
        existing_summary = self.db.get_latest_summary(user_id, timeframe)
        
        if existing_summary:
            summary = self._merge_summaries(existing_summary["summary"], summary)
        
        self.db.save_summary(user_id, timeframe, summary)

    def _generate_summary(self, conversations: List[Dict], timeframe: str) -> Dict:
        """Generate a summary from conversations"""
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversations
        ])

        prompt = f"""
        Analyze these {timeframe} conversations and create a structured summary with:
        1. Key Topics: Main subjects discussed
        2. Insights: Important realizations or decisions
        3. Patterns: Recurring themes or behaviors
        4. Action Items: Commitments or next steps
        5. Emotional Themes: Notable emotional patterns
        
        Conversations:
        {conversation_text}
        
        Format as JSON with these categories and include a relevance_score (1-10) for each item.
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing conversations and extracting meaningful patterns."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error generating summary: {e}")
            return {}

    def get_relevant_context(self, current_message: str, user_id: str) -> Dict:
        """Get relevant context from summaries for the current conversation"""
        summaries = self.db.get_all_summaries(user_id)
        
        prompt = f"""
        Find relevant context from these summaries for the current message:
        
        Current message: {current_message}
        
        Available Summaries:
        {json.dumps(summaries, indent=2)}
        
        Return only the most relevant items as JSON, with a relevance_score (1-10) for each item.
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at finding relevant context in conversation histories."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error getting context: {e}")
            return {}

    def _merge_summaries(self, old_summary: Dict, new_summary: Dict) -> Dict:
        """
        Intelligently merge old and new summaries while preserving important information
        """
        prompt = f"""
        Analyze and merge these two summaries, preserving the most relevant information:

        Previous Summary:
        {json.dumps(old_summary, indent=2)}

        New Summary:
        {json.dumps(new_summary, indent=2)}

        Rules for merging:
        1. Keep items with high relevance_score (7-10)
        2. Combine similar themes and update their scores
        3. Remove outdated or redundant information
        4. Maintain maximum 5 items per category
        5. Update action items based on completion status
        6. Note any evolving patterns or changes

        Return a merged JSON with the same structure as input summaries.
        Each item should have an updated relevance_score (1-10).
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing and synthesizing information, with a focus on identifying patterns and maintaining relevant context."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            merged = json.loads(response.choices[0].message.content)
            
            # Post-process the merged summary
            for category in merged:
                if isinstance(merged[category], list):
                    # Sort by relevance_score and keep top 5
                    merged[category] = sorted(
                        merged[category],
                        key=lambda x: x.get('relevance_score', 0),
                        reverse=True
                    )[:5]
            
            return merged
            
        except Exception as e:
            print(f"Error merging summaries: {e}")
            # If merge fails, return new summary as fallback
            return new_summary 