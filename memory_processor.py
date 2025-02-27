import openai
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from pydantic import BaseModel, Field
from logging_config import setup_logging

# Configure logging
logger = setup_logging()

class MemoryProcessor:
    def __init__(self, api_key: str, db_manager):
        self.api_key = api_key
        self.db = db_manager
        self.client = openai.OpenAI(api_key=api_key)
        logger.info("MemoryProcessor initialized")

    def process_conversation(self, user_id: str, conversation: Dict) -> None:
        """Process a new conversation and update memory summaries"""
        logger.info(f"Processing conversation for user {user_id}")
        
        # Get existing summaries
        daily_summary = self.db.get_latest_summary(user_id, "daily")
        weekly_summary = self.db.get_latest_summary(user_id, "weekly")
        
        # Process daily summary
        if self._needs_new_summary(daily_summary, "daily"):
            logger.info("Generating new daily summary")
            self._generate_and_save_summary(user_id, "daily", conversation)
        
        # Process weekly summary
        if self._needs_new_summary(weekly_summary, "weekly"):
            logger.info("Generating new weekly summary")
            self._generate_and_save_summary(user_id, "weekly", conversation)

    def _needs_new_summary(self, existing_summary: Optional[Dict], timeframe: str) -> bool:
        """Determine if a new summary needs to be generated"""
        if not existing_summary:
            logger.debug(f"No existing {timeframe} summary found")
            return True
            
        last_update = datetime.fromisoformat(existing_summary.get("last_updated", "2000-01-01"))
        current_time = datetime.now()
        
        thresholds = {
            "daily": timedelta(hours=24),
            "weekly": timedelta(days=7)
        }
        
        needs_update = current_time - last_update > thresholds[timeframe]
        logger.debug(f"{timeframe} summary needs update: {needs_update}")
        return needs_update

    def _generate_and_save_summary(self, user_id: str, timeframe: str, conversation: Dict) -> None:
        """Generate and save a new summary"""
        logger.info(f"Generating {timeframe} summary for user {user_id}")
        
        # Get relevant conversations
        conversations = self.db.get_conversations_for_timeframe(user_id, timeframe)
        logger.debug(f"Found {len(conversations)} conversations for {timeframe} summary")
        
        summary = self._generate_summary(conversations, timeframe)
        
        # Get existing summary to merge with
        existing_summary = self.db.get_latest_summary(user_id, timeframe)
        
        if existing_summary:
            logger.debug("Merging with existing summary")
            summary = self._merge_summaries(existing_summary["summary"], summary)
        
        self.db.save_summary(user_id, timeframe, summary)
        logger.info(f"Saved {timeframe} summary for user {user_id}")

    def _generate_summary(self, conversations: List[Dict], timeframe: str) -> Dict:
        """Generate a summary from conversations"""
        if not conversations:
            logger.debug("No conversations to summarize")
            return {}
        
        logger.debug(f"Generating summary for {len(conversations)} conversations")
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
        """

        # Update logging to be more concise
        logger.debug(f"Sending {timeframe} summary prompt to OpenAI")

        try:
            logger.debug("Calling OpenAI API for summary generation")
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing conversations and extracting meaningful patterns. Make sure relevance scores are between 1 and 10."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format=ConversationSummary
            )
            
            # Update logging to be more concise
            logger.debug("Received response from OpenAI API")

            try:
                json_response = json.loads(response.choices[0].message.content)
                logger.debug("Successfully parsed JSON response")
                
                # Validate response against schema
                validated_summary = ConversationSummary.model_validate(json_response)
                return validated_summary.model_dump()
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {e}")
                return {}
            except Exception as e:
                logger.error(f"Schema validation error: {e}")
                return {}
            
        except Exception as e:
            logger.error(f"OpenAI API error in _generate_summary: {e}")
            return {}

    def get_relevant_context(self, current_message: str, user_id: str) -> Dict:
        """Get relevant context from summaries for the current conversation"""
        logger.info(f"Getting relevant context for user {user_id}")

        summaries = self.db.get_all_summaries(user_id)
        if not summaries: 
            logger.debug("No summaries found")
            return {}

        logger.debug(f"Found {len(summaries)} summaries")
        prompt = f"""
        Find relevant context from these summaries for the current message:
        
        Current message: {current_message}
        
        Available Summaries:
        {json.dumps(summaries, indent=2)}
        
        Extract relevant information and return as JSON with this exact structure:
        {{
            "items": [
                {{
                    "content": "relevant piece of information",
                    "relevance_score": 8
                }}
            ]
        }}
        """

        try:
            logger.debug("Calling OpenAI API for context retrieval")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at finding relevant context in conversation histories."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                logger.debug(f"Found {len(result.get('items', []))} relevant context items")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {e}")
                logger.error(f"Raw response: {response.choices[0].message.content}")
                return {"items": []}
            
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return {"items": []}

    def _merge_summaries(self, old_summary: Dict, new_summary: Dict) -> Dict:
        """Intelligently merge old and new summaries while preserving important information"""
        logger.info("Merging summaries")
        
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

        # Log the prompt being sent
        logger.info("Sending prompt to OpenAI API from _merge_summaries:")
        logger.info(f"Prompt:\n{prompt}\n")

        try:
            logger.debug("Calling OpenAI API for summary merging")
            response = self.client.chat.completions.create(
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
            
            # Log the response
            logger.info("Response from OpenAI API:")
            logger.info(response.choices[0].message.content)
            
            merged = json.loads(response.choices[0].message.content)
            logger.debug("Successfully merged summaries")
            
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
            logger.error(f"Error in _merge_summaries: {e}")
            logger.warning("Falling back to new summary")
            return new_summary

# First define the schema models
class SummaryItem(BaseModel):
    content: str
    relevance_score: int = Field()

class ConversationSummary(BaseModel):
    key_topics: List[SummaryItem]
    insights: List[SummaryItem]
    patterns: List[SummaryItem]
    action_items: List[SummaryItem]
    emotional_themes: List[SummaryItem] 