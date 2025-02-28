import openai
from typing import Dict, List, Any, Optional, Tuple
import json
import logging
from datetime import datetime
from pydantic import BaseModel, Field
from database import DatabaseManager
from memory_processor import MemoryProcessor
from logging_config import log_structured_output_request, log_structured_output_response


class MessageAnalysisModel(BaseModel):
    """Model for message analysis results"""
    primary_intent: str = Field(description="What the user is primarily seeking")
    emotional_state: str = Field(description="The emotional state conveyed in the message") 
    urgency_level: int = Field(description="How urgent the message seems on a scale of 1-10")
    topics: List[str] = Field(description="Main topics mentioned in the message")
    potential_triggers: Optional[str] = Field(description="Any potential nervous system triggers detected")


class ActionItemModel(BaseModel):
    """Model for extracted action items"""
    content: str = Field(description="The action item text")


class ActionItemsResponseModel(BaseModel):
    """Container for multiple action items"""
    items: List[ActionItemModel] 

class ContextManager:
    """
    Integrated context manager that unifies database operations and memory processing
    to provide comprehensive context for the AI coach.
    """
    
    def __init__(self, api_key: str, db_path: str = "nervous_system_coach.db"):
        self.api_key = api_key
        self.db = DatabaseManager(db_path)
        self.memory_processor = MemoryProcessor(api_key, self.db)
        self.client = openai.OpenAI(api_key=api_key)
        self.logger = logging.getLogger('nervous_system_coach.context_manager')
    
    def process_user_message(self, user_id: str, message_content: str) -> Tuple[int, Dict[str, Any]]:
        """
        Process a new user message: store it, analyze it, and extract insights
        
        Args:
            user_id: The user's ID
            message_content: The content of the user's message
            
        Returns:
            Tuple of (message_id, message_analysis)
        """
        # Save message to conversations
        message_id = self._save_message(user_id, message_content, "user")
        
        # Analyze message
        analysis = self._analyze_message(message_content, user_id)
        
        # Save analysis
        if analysis:
            self.db.save_message_analysis(message_id, user_id, analysis)
            
            # Process topics
            if "topics" in analysis:
                for topic in analysis["topics"]:
                    self.db.update_or_create_topic(user_id, topic, 0.8)  # Default relevance
        
        # Trigger asynchronous memory processing
        # Note: In a real app, this might be done asynchronously
        self.memory_processor.process_conversation_for_insights(user_id, {
            "role": "user",
            "content": message_content
        })
        
        return message_id, analysis
    
    def process_ai_response(self, user_id: str, response_content: str) -> int:
        """
        Process AI response: store it and extract action items
        
        Args:
            user_id: The user's ID
            response_content: The content of the AI's response
            
        Returns:
            The message ID
        """
        # Save message
        message_id = self._save_message(user_id, response_content, "assistant")
        
        # Extract and save action items
        action_items = self._extract_action_items(response_content)
        for item in action_items:
            self.db.save_action_item(user_id, item, message_id)
        
        # Trigger asynchronous memory processing
        # Note: In a real app, this might be done asynchronously
        self.memory_processor.process_conversation_for_insights(user_id, {
            "role": "assistant",
            "content": response_content
        })
        
        return message_id
    
    def get_ai_response(self, user_id: str, message_content: str, model: str = "gpt-4o-mini") -> str:
        """
        Get AI response for a user message with enriched context
        
        Args:
            user_id: The user's ID
            message_content: The content of the user's message
            model: The model to use for the response
            
        Returns:
            The AI's response
        """
        # Process user message
        message_id, _ = self.process_user_message(user_id, message_content)
        
        # Build comprehensive context
        context = self.memory_processor.get_comprehensive_context(message_content, user_id)
        
        # Format context for LLM
        formatted_context = self.memory_processor.format_context_for_llm(context)
        
        # Fetch user profile
        profile = self.db.get_user_profile(user_id)
        
        # System instructions with formatted context
        system_content = profile.get('custom_instructions', '')
        system_content += "\n\n" + formatted_context
        
        # Get recent conversation messages
        conversation_history = self.db.get_conversation_history(user_id)[-10:]  # Last 10 messages
        
        # Build messages for API
        messages = [
            {"role": "system", "content": system_content}
        ]
        
        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message_content
        })
        
        # Get response
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
            
            response_content = response.choices[0].message.content
            
            # Process AI response
            self.process_ai_response(user_id, response_content)
            
            return response_content
        
        except Exception as e:
            self.logger.error(f"Error getting AI response: {e}")
            return f"Error communicating with AI service: {str(e)}"
    
    def _save_message(self, user_id: str, content: str, role: str) -> int:
        """Save a message to the database with deduplication"""
        # Get or create session
        session_id = self.db.get_current_session_id(user_id)
        
        # Use the enhanced save_conversation method from DatabaseManager
        return self.db.save_conversation(user_id, role, content)
    
    def _analyze_message(self, message: str, user_id: str) -> Dict[str, Any]:
        """Analyze a message for intent, emotional state, etc. using structured output"""
        if not message:
            return {}
                
        try:
            # Use OpenAI's structured output capabilities
            try:
                messages = [
                {"role": "system", "content": "Analyze the user's message to understand their intent, emotional state, and needs."},
                {"role": "user", "content": f"Analyze this message from a user to their AI coach: '{message}'"}
                ]
            
                model = "gpt-4o-mini"
            
                log_structured_output_request(self.logger, model, messages, MessageAnalysisModel)
            

                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=MessageAnalysisModel
                )
            
                parsed_response = completion.choices[0].message.parsed
            
                log_structured_output_response(self.logger, model, parsed_response)
                
                # Convert to dictionary for storage
                return parsed_response.model_dump()
                
            except Exception as e:
                self.logger.error(f"Error using structured output for message analysis: {e}")
                # Return default structure on error
                return {
                    "primary_intent": "unclear",
                    "emotional_state": "neutral",
                    "urgency_level": 5,
                    "topics": ["general inquiry"],
                    "potential_triggers": "none detected"
                }
                    
        except Exception as e:
            self.logger.error(f"Error analyzing message: {e}")
            return {
                "primary_intent": "unknown",
                "emotional_state": "unknown",
                "urgency_level": 5,
                "topics": [],
                "potential_triggers": "analysis failed"
            }

    
    def _extract_action_items(self, response: str) -> List[str]:
        """Extract action items from an AI response using structured output"""
        if not response:
            return []
        
        try:
            # Use OpenAI's structured output capabilities
            try:
                messages = [
                    {"role": "system", "content": "Extract action items, next steps, or commitments from this AI coach response."},
                    {"role": "user", "content": f"Extract action items from this AI coach response: '{response}'"}
                ]
            
                model = "gpt-4o-mini"
                
                # ADD THIS: Log the request
                log_structured_output_request(self.logger, model, messages, ActionItemsResponseModel)
                
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=ActionItemsResponseModel
                )
                
                parsed_response = completion.choices[0].message.parsed

                log_structured_output_response(self.logger, model, parsed_response)
                
                # Extract just the content strings from the items
                return [item.content for item in parsed_response.items]
                
            except Exception as e:
                self.logger.error(f"Error using structured output for action items: {e}")
                # Return empty list on error
                return []
                    
        except Exception as e:
            self.logger.error(f"Error extracting action items: {e}")
            return []
    
    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive summary of the user for dashboard display
        
        Returns:
            A dictionary with user insights, metrics, and trends
        """
        result = {
            "profile": self.db.get_user_profile(user_id),
            "active_topics": self.db.get_active_topics(user_id),
            "pending_actions": self.db.get_pending_action_items(user_id),
            "insights": self.db.get_user_insights(user_id, min_confidence=0.7),
            "recent_analyses": self.db.get_message_analysis(user_id, limit=5)
        }
        
        # Add summaries
        daily_summary = self.db.get_latest_summary(user_id, "daily")
        weekly_summary = self.db.get_latest_summary(user_id, "weekly")
        
        if daily_summary:
            result["daily_summary"] = daily_summary["summary"]
        if weekly_summary:
            result["weekly_summary"] = weekly_summary["summary"]
        
        return result
    
    def track_progress(self, user_id: str, metric_name: str, value: float, notes: Optional[str] = None) -> bool:
        """
        Track progress on a specific metric
        
        Args:
            user_id: The user's ID
            metric_name: The name of the metric to track
            value: The value of the metric
            notes: Optional notes about the metric
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.db.save_progress_metric(user_id, metric_name, value, notes)
            return True
        except Exception as e:
            self.logger.error(f"Error tracking progress: {e}")
            return False
    
    def mark_action_completed(self, action_id: int) -> bool:
        """
        Mark an action item as completed
        
        Args:
            action_id: The ID of the action item
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_time = datetime.now().isoformat()
            return self.db.update_action_item_status(action_id, "completed", current_time)
        except Exception as e:
            self.logger.error(f"Error marking action completed: {e}")
            return False