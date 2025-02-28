import openai
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Literal
import json
import logging
from datetime import datetime, timedelta
from logging_config import log_structured_output_request, log_structured_output_response



# ===== Pydantic Models for Structured Output =====

class UserInsight(BaseModel):
    """Model for user insights extracted from messages"""
    category: Literal["value", "challenge", "preference", "pattern", "trigger", "strength"]
    content: str
    confidence: float


class UserInsightsResponse(BaseModel):
    """Container for multiple user insights"""
    insights: List[UserInsight] 


class MessageAnalysis(BaseModel):
    """Model for analyzing user messages"""
    primary_intent: str 
    emotional_state: str 
    urgency_level: int
    topics: List[str]
    potential_triggers: Optional[str] 


class TopicItem(BaseModel):
    """Model for a conversation topic"""
    name: str
    relevance: float 


class TopicsResponse(BaseModel):
    """Container for multiple topics"""
    topics: List[TopicItem]


class ActionItem(BaseModel):
    """Model for action items extracted from AI responses"""
    content: str


class ActionItemsResponse(BaseModel):
    """Container for multiple action items"""
    items: List[ActionItem] 


class EmotionalMetrics(BaseModel):
    """Model for emotional metrics extracted from user messages"""
    stress_level: Optional[float] 
    anxiety_level: Optional[float]
    positivity: Optional[float] 
    activation: Optional[float] 

class SummaryContent(BaseModel):
    """Model for structured summary content"""
    key_themes: List[str] = Field(description="Main themes discussed during this period")
    emotional_journey: str = Field(description="Overview of emotional states and changes")
    insights_gained: List[str] = Field(description="Key insights or realizations")
    progress_made: str = Field(description="Progress on goals or challenges")
    action_items: List[str] = Field(description="Action items identified or completed")
    recommended_focus: str = Field(description="Suggested areas of focus going forward")

class MemoryProcessor:
    """
    Enhanced memory processor that focuses on direct insight extraction and context building
    without relying on summarization.
    """
    
    def __init__(self, api_key: str, db_manager):
        self.api_key = api_key
        self.db = db_manager
        self.client = openai.OpenAI(api_key=api_key)
        self.logger = logging.getLogger('nervous_system_coach.enhanced_memory')
    
    def process_conversation_for_insights(self, user_id: str, conversation: Dict):
        """
        Process a conversation message to extract insights and update the user profile
        
        Args:
            user_id: The user's ID
            conversation: A dict containing message details with 'role' and 'content'
        """
        message_content = conversation.get("content", "")
        message_role = conversation.get("role", "")
        
        # Add timestamp if not present
        if "timestamp" not in conversation:
            conversation["timestamp"] = datetime.now().isoformat()
        
        if not message_content or not message_role:
            self.logger.warning("Skipping empty message in process_conversation_for_insights")
            return
        
        self.logger.info(f"Processing {message_role} message for insights")
        
        # 1. Extract user insights if this is a user message
        if message_role == "user":
            try:
                insights_response = self._extract_user_insights_from_message(user_id, message_content)
                
                # Save extracted insights to database
                if insights_response and insights_response.insights:
                    for insight in insights_response.insights:
                        try:
                            self.logger.info(f"Saving insight: {insight.category} - {insight.content}")
                            self.db.save_user_insight(
                                user_id=user_id,
                                category=insight.category,
                                content=insight.content,
                                confidence=insight.confidence,
                                source_message_ids=[]
                            )
                        except Exception as e:
                            self.logger.error(f"Error saving insight: {e}")
            except Exception as e:
                self.logger.error(f"Error in user insight extraction: {e}")
        
        # 2. Extract action items if this is an AI message
        if message_role == "assistant":
            try:
                action_items_response = self._extract_action_items_from_message(message_content)
                
                # Save action items
                if action_items_response and action_items_response.items:
                    for item in action_items_response.items:
                        try:
                            self.logger.info(f"Extracted action item: {item.content}")
                            self.db.save_action_item(user_id, item.content, 0)
                        except Exception as e:
                            self.logger.error(f"Error saving action item: {e}")
            except Exception as e:
                self.logger.error(f"Error in action item extraction: {e}")
        
        # 3. Update topics for both user and AI messages
        try:
            topics_response = self._extract_topics_from_message(message_content)
            if topics_response and topics_response.topics:
                for topic in topics_response.topics:
                    try:
                        self.db.update_or_create_topic(
                            user_id, 
                            topic.name, 
                            topic.relevance
                        )
                    except Exception as e:
                        self.logger.error(f"Error updating topic: {e}")
        except Exception as e:
            self.logger.error(f"Error in topic extraction: {e}")
        
        # 4. Extract and save emotional state metrics if this is a user message
        if message_role == "user":
            try:
                emotional_metrics = self._extract_emotional_metrics(message_content)
                
                # Convert to dict and filter None values
                if emotional_metrics:
                    metrics_dict = {k: v for k, v in emotional_metrics.dict().items() if v is not None}
                    
                    for metric_name, value in metrics_dict.items():
                        try:
                            self.db.save_progress_metric(
                                user_id, 
                                metric_name, 
                                value,
                                f"Extracted from message: {message_content[:50]}..."
                            )
                        except Exception as e:
                            self.logger.error(f"Error saving metric: {e}")
            except Exception as e:
                self.logger.error(f"Error in emotional metrics extraction: {e}")
    
    def get_comprehensive_context(self, current_message: str, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive context that includes immediate, short-term, and long-term memory
        
        Args:
            current_message: The user's current message
            user_id: The user's ID
            
        Returns:
            Dict containing various context layers
        """
        context = {
            "immediate_context": self._get_immediate_context(user_id),
            "user_profile": self._get_user_profile(user_id),
            "current_query_analysis": self._analyze_current_query(current_message, user_id),
            "active_topics": self._get_active_topics(user_id),
            "progress_metrics": self._get_progress_metrics(user_id)
        }
        
        return context
    
    def _extract_user_insights_from_message(self, user_id: str, message: str) -> UserInsightsResponse:
        """Extract insights about the user from a single message using structured output"""
        if not message:
            return UserInsightsResponse()
        
        try:
            # Get user profile and recent conversations for context
            profile = self.db.get_user_profile(user_id)
            recent_messages = self.db.get_conversation_history(user_id)[-5:]
            
            # Check if we actually have messages before processing
            if not recent_messages:
                self.logger.info("No conversation history available for insight extraction")
                return UserInsightsResponse()
            
            recent_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
            
            # Use OpenAI's structured output capabilities
            try:
                messages = [
                {"role": "system", "content": "Extract insights about the user from their message."},
                {"role": "user", "content": f"""
                Recent conversation:
                {recent_context}
                
                Current message:
                {message}
                
                Extract insights with confidence >= 0.6. Valid categories are: value, challenge, preference, pattern, trigger, strength.
                """}
                ]
            
                model = "gpt-4o-mini"
                log_structured_output_request(self.logger, model, messages, UserInsightsResponse)
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=UserInsightsResponse
                )
                
                parsed_response = completion.choices[0].message.parsed
                
                log_structured_output_response(self.logger, model, parsed_response)
                
                return parsed_response
                
            except Exception as e:
                self.logger.error(f"Error using structured output for insights: {e}")
                # Return empty response on error
                return UserInsightsResponse()
                
        except Exception as e:
            self.logger.error(f"Error extracting user insights: {e}")
            return UserInsightsResponse()
    
    def _call_llm_for_action_items(self, message: str) -> List[str]:
        """
        Call LLM to extract action items from text
        
        Args:
            message: The message to extract action items from
            
        Returns:
            List of action item strings
        """
        if not message:
            return []
        
        try:
            prompt = f"""
            Extract any action items, next steps, or commitments mentioned in this AI coach response:
            
            Response: "{message}"
            
            Return a JSON array of strings, with each string being a clear action item.
            Only include actual action items or commitments, not general advice or information.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You extract action items from text. Be precise and concise."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            try:
                result = json.loads(response.choices[0].message.content)
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict) and "items" in result:
                    return result["items"]
                return []
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse action items response as JSON: {e}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error calling LLM for action items: {e}")
            return []

    
    def _extract_action_items_from_message(self, message: str) -> ActionItemsResponse:
        """Extract action items from an AI message using structured output"""
        if not message:
            return ActionItemsResponse()
        
        try:
            # Use OpenAI's structured output capabilities
            try:
                messages = [
                {"role": "system", "content": "Extract action items, next steps, or commitments from this AI coach response."},
                {"role": "user", "content": f"Extract action items from this AI coach response: '{message}'"}
                ]
            
                model = "gpt-4o-mini"
            
                log_structured_output_request(self.logger, model, messages, ActionItemsResponse)

                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=ActionItemsResponse
                )
                parsed_response = completion.choices[0].message.parsed
                log_structured_output_response(self.logger, model, parsed_response)
                
                return parsed_response
                    
            except Exception as e:
                self.logger.error(f"Error using structured output for action items: {e}")
                # Return empty response on error
                return ActionItemsResponse()
            
        except Exception as e:
            self.logger.error(f"Error extracting action items: {e}")
            return ActionItemsResponse()
    
    def _extract_topics_from_message(self, message: str) -> TopicsResponse:
        """Extract topics from a message with relevance scores using structured output"""
        if not message:
            return TopicsResponse()
        
        try:
            # Use OpenAI's structured output capabilities
            try:
                messages = [
                    {"role": "system", "content": "Extract the main topics discussed in this message with relevance scores."},
                    {"role": "user", "content": f"Extract the main topics from this message: '{message}'"}
                ]
                
                model = "gpt-4o-mini"            
                log_structured_output_request(self.logger, model, messages, TopicsResponse)
        
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=TopicsResponse
                )
            
                parsed_response = completion.choices[0].message.parsed           
                log_structured_output_response(self.logger, model, parsed_response)
                
                return parsed_response
                
            except Exception as e:
                self.logger.error(f"Error using structured output for topics: {e}")
                # Return empty response on error
                return TopicsResponse()
            
        except Exception as e:
            self.logger.error(f"Error extracting topics: {e}")
            return TopicsResponse()

    
    
    def _extract_emotional_metrics(self, message: str) -> EmotionalMetrics:
        """Extract emotional state metrics from a user message using structured output"""
        if not message:
            return EmotionalMetrics()
        
        try:
            # Use OpenAI's structured output capabilities
            try:
                messages = [
                {"role": "system", "content": "Analyze the emotional state in this message using numerical metrics from 0-10."},
                {"role": "user", "content": f"Analyze the emotional metrics in this message: '{message}'"}
                ]
            
                model = "gpt-4o-mini"
                log_structured_output_request(self.logger, model, messages, EmotionalMetrics)
                
                # Existing code
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=EmotionalMetrics
                )
                
                parsed_response = completion.choices[0].message.parsed
                log_structured_output_response(self.logger, model, parsed_response)
                
                return parsed_response
                
            except Exception as e:
                self.logger.error(f"Error using structured output for emotional metrics: {e}")
                # Return empty response on error
                return EmotionalMetrics()
            
        except Exception as e:
            self.logger.error(f"Error extracting emotional metrics: {e}")
            return EmotionalMetrics()

    
    def _get_immediate_context(self, user_id: str) -> Dict[str, Any]:
        """Get the most recent conversation messages for immediate context"""
        # Get the last 10 messages for immediate context
        recent_messages = self.db.get_conversation_history(user_id)[-10:]
        
        return {
            "recent_messages": recent_messages,
            "message_count": len(recent_messages)
        }
    
    def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile including codex vitae and insights"""
        # Get user profile and codex vitae
        profile = self.db.get_user_profile(user_id)
        
        # Extract codex vitae insights
        codex_vitae = profile['codex_vitae'] if profile else {}
        
        # Get high-confidence insights
        insights = self.db.get_user_insights(user_id, min_confidence=0.7)
        
        # Group insights by category
        grouped_insights = {}
        for insight in insights:
            category = insight["category"]
            if category not in grouped_insights:
                grouped_insights[category] = []
            grouped_insights[category].append(insight["content"])
        
        return {
            "codex_vitae": codex_vitae,
            "insights": grouped_insights,
            "coach_style": {
                "name": profile.get('coach_name', ''),
                "vibes": profile.get('coach_vibes', '')
            }
        }
    
    def _analyze_current_query(self, message: str, user_id: str) -> MessageAnalysis:
        """Analyze the current query for intent, emotional state, and relevance using structured output"""
        default_analysis = MessageAnalysis(
            primary_intent="unknown",
            emotional_state="neutral",
            urgency_level=5,
            topics=[],
            potential_triggers="none detected"
        )
        
        if not message:
            return default_analysis
        
        try:

            messages = [
            {"role": "system", "content": "Analyze the user's message to understand their intent, emotional state, and needs."},
            {"role": "user", "content": f"Analyze this message from a user to their AI coach: '{message}'"}
            ]
        
            model = "gpt-4o-mini"
        
            log_structured_output_request(self.logger, model, messages, MessageAnalysis)
        

            completion = self.client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=MessageAnalysis
            )
            
            parsed_response = completion.choices[0].message.parsed

            log_structured_output_response(self.logger, model, parsed_response)
        
            return parsed_response
            
        except Exception as e:
            self.logger.error(f"Error analyzing current query: {e}")
            return default_analysis
    
    def _get_active_topics(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active conversation topics and their progression"""
        # Get active topics from database
        return self.db.get_active_topics(user_id, limit=5)
    
    def _get_progress_metrics(self, user_id: str) -> Dict[str, Any]:
        """Extract measurable progress metrics from conversations"""
        # Get pending action items
        action_items = self.db.get_pending_action_items(user_id)
        
        # Get recent emotional metrics
        metrics = {}
        for metric_name in ["stress_level", "anxiety_level", "positivity", "activation"]:
            history = self.db.get_metric_history(user_id, metric_name, days=7)
            if history:
                metrics[metric_name] = history
        
        return {
            "action_items": action_items,
            "emotional_metrics": metrics
        }
    
    def format_context_for_llm(self, context: Dict[str, Any]) -> str:
        """Format the comprehensive context into a string for LLM prompt"""
        formatted = []
        
        # Add immediate context (recent messages)
        if "immediate_context" in context and context["immediate_context"].get("recent_messages"):
            formatted.append("RECENT CONVERSATION:")
            for msg in context["immediate_context"]["recent_messages"][-3:]:  # Last 3 messages
                formatted.append(f"{msg['role']}: {msg['content']}")
            formatted.append("")
        
        # Add user profile insights
        if "user_profile" in context:
            profile = context["user_profile"]
            
            if profile.get("insights"):
                insights = profile["insights"]
                
                formatted.append("USER INSIGHTS:")
                
                for category, items in insights.items():
                    if items:
                        formatted.append(f"{category.capitalize()}: {', '.join(items[:3])}")
                
                formatted.append("")
            
            # Add codex vitae highlights
            if profile.get("codex_vitae"):
                codex = profile["codex_vitae"]
                formatted.append("FROM CODEX VITAE:")
                
                priority_keys = ["core_values", "reactivity_triggers", "burnout_warning_signs", "joy_triggers"]
                for key in priority_keys:
                    if key in codex and codex[key]:
                        formatted.append(f"{key.replace('_', ' ').capitalize()}: {codex[key]}")
                
                formatted.append("")
        
        # Add current query analysis
        if "current_query_analysis" in context and context["current_query_analysis"]:
            analysis = context["current_query_analysis"]
            
            formatted.append("CURRENT QUERY ANALYSIS:")
            if "primary_intent" in analysis:
                formatted.append(f"Intent: {analysis['primary_intent']}")
            
            if "emotional_state" in analysis:
                formatted.append(f"Emotional State: {analysis['emotional_state']}")
            
            if "potential_triggers" in analysis:
                formatted.append(f"Potential Triggers: {analysis['potential_triggers']}")
            
            formatted.append("")
        
        # Add active topics
        if "active_topics" in context and context["active_topics"]:
            formatted.append("ACTIVE TOPICS:")
            for topic in context["active_topics"]:
                formatted.append(f"- {topic['name']}")
            formatted.append("")
        
        # Add progress metrics
        if "progress_metrics" in context and context["progress_metrics"].get("action_items"):
            formatted.append("ACTION ITEMS:")
            for item in context["progress_metrics"]["action_items"]:
                formatted.append(f"- {item['content']}")
            formatted.append("")
        
        return "\n".join(formatted)

    def get_relevant_context(self, query, user_id):
        """
        Get relevant context from the database based on the query
        """
        # This is a placeholder - we're actually generating comprehensive context
        # for use in the AI responses
        return {"items": []}

    # ========== SUMMARY GENERATION METHODS ==========

    def generate_summaries(self, user_id: str):
        """
        Generate both daily and weekly summaries if needed
        
        Args:
            user_id: The user's ID
        """
        self.logger.info(f"Checking if summaries need to be generated for user {user_id}")
        
        try:
            # Check when the last daily summary was generated
            daily_summary = self.db.get_latest_summary(user_id, "daily")
            if not daily_summary or self._summary_needed(daily_summary, "daily"):
                self.logger.info("Generating daily summary")
                self.generate_timeframe_summary(user_id, "daily")
            
            # Check when the last weekly summary was generated
            weekly_summary = self.db.get_latest_summary(user_id, "weekly")
            if not weekly_summary or self._summary_needed(weekly_summary, "weekly"):
                self.logger.info("Generating weekly summary")
                self.generate_timeframe_summary(user_id, "weekly")
        except Exception as e:
            self.logger.error(f"Error in generate_summaries: {e}")

    def _summary_needed(self, last_summary: Dict, timeframe: str) -> bool:
        """
        Determine if a new summary needs to be generated based on the last summary time
        
        Args:
            last_summary: The most recent summary for this timeframe
            timeframe: 'daily' or 'weekly'
            
        Returns:
            True if a new summary should be generated
        """
        if not last_summary:
            return True
            
        last_updated = datetime.fromisoformat(last_summary["last_updated"]) if isinstance(last_summary["last_updated"], str) else last_summary["last_updated"]
        current_time = datetime.now()
        
        if timeframe == "daily":
            # Daily summaries should be generated once per day
            return (current_time - last_updated).days >= 1
        elif timeframe == "weekly":
            # Weekly summaries should be generated once per week
            return (current_time - last_updated).days >= 7
        
        return False

    def generate_timeframe_summary(self, user_id: str, timeframe: str):
        """
        Generate a summary for a specific timeframe using structured output
        
        Args:
            user_id: The user's ID
            timeframe: 'daily' or 'weekly'
        """
        try:
            # Get user profile for context
            profile = self.db.get_user_profile(user_id)
            if not profile:
                self.logger.warning(f"Cannot generate summary for user {user_id} - profile not found")
                return
            
            # Get conversations for the timeframe
            conversations = self.db.get_conversations_for_timeframe(user_id, timeframe)
            
            # If no conversations found, create an appropriate "no activity" summary
            if not conversations:
                self.logger.info(f"No conversations found for {timeframe} summary")
                no_activity_summary = SummaryContent(
                    key_themes=["No activity"],
                    emotional_journey="There was no coaching activity during this period.",
                    insights_gained=["Consider re-engaging with the coaching process"],
                    progress_made="No coaching interactions to assess progress during this period.",
                    action_items=["Schedule a check-in session", "Review previous goals"],
                    recommended_focus="Consider what support would be most valuable right now and how to re-engage with the coaching process."
                )
                self.db.save_summary(user_id, timeframe, no_activity_summary.model_dump())
                self.logger.info(f"Created 'no activity' summary for {timeframe}")
                return
            
            # Format conversations for the LLM
            formatted_conversations = self._format_conversations_for_summary(conversations)
            
            # Get user's codex vitae for context
            codex_vitae = profile.get('codex_vitae', {})
            codex_context = self._format_codex_vitae_context(codex_vitae)
            
            # Generate summary using structured output
            try:
                messages = [
                {"role": "system", "content": "Generate a structured summary of coaching conversations."},
                {"role": "user", "content": f"""
                You are a nervous system-focused AI coach. 
                Generate a summary of the client's conversations over the past {timeframe}.
                
                Here are the conversations:
                {formatted_conversations}
                
                {codex_context}
                
                Generate a structured summary that captures the key themes, emotional journey, 
                insights gained, progress made, action items, and recommended focus areas.
            """}
                ]
        
                model = "gpt-4o"
                log_structured_output_request(self.logger, model, messages, SummaryContent)
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=SummaryContent
                )

                summary = completion.choices[0].message.parsed
                log_structured_output_response(self.logger, model, summary)

                # Save the summary to the database
                self.db.save_summary(user_id, timeframe, summary.model_dump())
                self.logger.info(f"Successfully generated and saved {timeframe} summary for user {user_id}")
                
            except Exception as e:
                self.logger.error(f"Error generating summary with structured output: {e}")
                # Create fallback summary
                fallback_summary = self._create_fallback_summary()
                self.db.save_summary(user_id, timeframe, fallback_summary)
                self.logger.info(f"Created fallback summary for {timeframe}")
                
        except Exception as e:
            self.logger.error(f"Error in generate_timeframe_summary: {e}")

    def _format_codex_vitae_context(self, codex_vitae: Dict) -> str:
        """Format codex vitae for inclusion in prompts"""
        if not codex_vitae:
            return ""
        
        context = "Important context from client's Codex Vitae:\n"
        priority_keys = ["core_values", "reactivity_triggers", "burnout_warning_signs", "joy_triggers"]
        
        for key in priority_keys:
            if key in codex_vitae and codex_vitae[key]:
                formatted_key = key.replace('_', ' ').capitalize()
                context += f"- {formatted_key}: {codex_vitae[key]}\n"
        
        return context

    def _format_conversations_for_summary(self, conversations: List[Dict]) -> str:
        """
        Format conversation history for inclusion in summary prompt
        
        Args:
            conversations: List of conversation messages with role and content
            
        Returns:
            Formatted string of conversations
        """
        if not conversations:
            return "No conversations in this period."
        
        formatted = []
        for i, msg in enumerate(conversations):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role and content:
                # Truncate very long messages
                if len(content) > 500:
                    content = content[:497] + "..."
                
                # Add role and content to formatted list
                formatted.append(f"{role.capitalize()}: {content}")
        
        return "\n\n".join(formatted)

    def _build_simple_summary_prompt(self, timeframe: str, conversations: str, profile: Dict) -> str:
        """
        Build a simplified prompt for the LLM to generate a summary when we don't have advanced context
        
        Args:
            timeframe: 'daily' or 'weekly'
            conversations: Formatted conversation history
            profile: User profile data
            
        Returns:
            Prompt string for the LLM
        """
        time_description = "day" if timeframe == "daily" else "week"
        
        # Get coach name and vibes from profile, or use defaults
        coach_name = profile.get("coach_name", "AI Coach")
        coach_vibes = profile.get("coach_vibes", "supportive and insightful")
        
        # Get codex vitae for context
        codex_vitae = profile.get('codex_vitae', {})
        codex_context = ""
        
        if codex_vitae:
            codex_context = "\nImportant context from client's Codex Vitae:\n"
            priority_keys = ["core_values", "reactivity_triggers", "burnout_warning_signs", "joy_triggers"]
            for key in priority_keys:
                if key in codex_vitae and codex_vitae[key]:
                    formatted_key = key.replace('_', ' ').capitalize()
                    codex_context += f"- {formatted_key}: {codex_vitae[key]}\n"
        
        prompt = f"""
        You are {coach_name}, a nervous system-focused AI coach with {coach_vibes} vibes. 
        You need to generate a summary of your client's conversations over the past {time_description}. 
        This summary will help you maintain continuity in your coaching relationship and identify patterns.
        
        Here are the conversations from the past {time_description}:
        
        {conversations}
        {codex_context}
        
        Based on the above information, create a structured summary with the following elements:
        1. Key themes discussed during this period (3-5 bullet points)
        2. Emotional journey - overview of emotional states and changes
        3. Insights gained - key realizations or discoveries (3-5 bullet points)
        4. Progress made on goals or challenges (1-2 paragraphs)
        5. Action items identified or completed (3-5 bullet points)
        6. Recommended focus areas going forward (1-2 paragraphs)
        
        Format your response as a JSON structure with these exact fields:
        {{
            "key_themes": ["theme1", "theme2", "theme3"],
            "emotional_journey": "Text describing emotional journey",
            "insights_gained": ["insight1", "insight2", "insight3"],
            "progress_made": "Text describing progress",
            "action_items": ["action1", "action2", "action3"],
            "recommended_focus": "Text describing recommended focus"
        }}
        
        Make your summary specific, personal, and actionable.
        """
        
        return prompt

    def _generate_summary_with_llm(self, prompt: str) -> Dict:
        """
        Use OpenAI's API to generate a summary from conversations
        
        Args:
            prompt: The prompt for the LLM
            
        Returns:
            Dictionary containing the structured summary
        """
        try:
            # First try using beta.chat.completions.parse with Pydantic model
            try:
                messages = [
                {"role": "system", "content": "Generate a structured summary of coaching conversations."},
                {"role": "user", "content": prompt}
                ]
            
                model = "gpt-4o"
                log_structured_output_request(self.logger, model, messages, SummaryContent)
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=SummaryContent
                )
                
                parsed_response = completion.choices[0].message.parsed
                log_structured_output_response(self.logger, model, parsed_response)

                return parsed_response.model_dump()

            except Exception as e:
                self.logger.error(f"Error parsing summary with beta.chat.completions.parse: {e}")
                
                # Fallback to regular completion with JSON formatting
                response = self.client.chat.completions.create(
                    model="gpt-4o",  # Using a more capable model for summaries
                    messages=[
                        {"role": "system", "content": "Generate a structured summary of coaching conversations."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                
                try:
                    result = json.loads(response.choices[0].message.content)
                    # Validate that the result has the expected fields
                    expected_fields = [
                        "key_themes", "emotional_journey", "insights_gained", 
                        "progress_made", "action_items", "recommended_focus"
                    ]
                    for field in expected_fields:
                        if field not in result:
                            result[field] = [] if field in ["key_themes", "insights_gained", "action_items"] else ""
                    
                    return result
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error parsing summary JSON: {e}")
                    # Create fallback summary if JSON parsing fails
                    return self._create_fallback_summary()
        except Exception as e:
            self.logger.error(f"Error generating summary with LLM: {e}")
            return self._create_fallback_summary()

    def _create_fallback_summary(self) -> Dict:
        """Create a fallback summary when generation fails"""
        fallback = SummaryContent(
            key_themes=["Technical error prevented detailed analysis"],
            emotional_journey="Unable to analyze emotional journey due to technical limitations.",
            insights_gained=["Check conversation directly for insights"],
            progress_made="Summary generation encountered an error. Please review conversations directly.",
            action_items=["Review conversation history manually", "Try generating summary again later"],
            recommended_focus="Addressing immediate client needs while technical issues are resolved."
        )
        return fallback.model_dump()