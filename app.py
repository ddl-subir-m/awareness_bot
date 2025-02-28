import streamlit as st
import openai
from summary_scheduler import SummaryScheduler

from pathlib import Path
from prompts import NERVOUS_SYSTEM_PROMPTS, ADDITIONAL_PROMPTS, get_default_instructions, ADDITIONAL_COACHING_PROMPT
from custom_css import css
from database import DatabaseManager
from memory_processor import MemoryProcessor
from context_manager import ContextManager  
from logging_config import setup_logging, log_llm_request, log_llm_response
from datetime import datetime, timedelta

# Configure logging
logger = setup_logging()

# Set page configuration
st.set_page_config(
    page_title="Nervous System AI Coach",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown(css, unsafe_allow_html=True)

# Initialize session state variables
if 'openai_client' not in st.session_state:
    st.session_state.openai_client = None
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'codex_vitae' not in st.session_state:
    st.session_state.codex_vitae = {}
if 'custom_instructions' not in st.session_state:
    st.session_state.custom_instructions = ""
if 'prompts' not in st.session_state:
    st.session_state.prompts = []
if 'coach_name' not in st.session_state:
    st.session_state.coach_name = ""
if 'coach_vibes' not in st.session_state:
    st.session_state.coach_vibes = ""
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "gpt-4o-mini"
if 'template_initialized' not in st.session_state:
    st.session_state.template_initialized = False
if 'name' not in st.session_state:
    st.session_state.name = ""
if 'passphrase' not in st.session_state:
    st.session_state.passphrase = ""
if 'current_prompt' not in st.session_state:
    st.session_state.current_prompt = ""
if 'current_input' not in st.session_state:
    st.session_state.current_input = ""
if 'summary_scheduler' not in st.session_state:
    st.session_state.summary_scheduler = None
if 'memory_processor' not in st.session_state:
    st.session_state.memory_processor = None



# Initialize database in session state
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()

# Initialize conversation history
st.session_state.conversation_history = []

def initialize_memory_services():
    """Initialize memory processor and summary scheduler if needed"""
    if 'api_key' in st.session_state and st.session_state.api_key:
        # Initialize memory processor
        if 'memory_processor' not in st.session_state or not st.session_state.memory_processor:
            st.session_state.memory_processor = MemoryProcessor(st.session_state.api_key, st.session_state.db)
            logger.info("Memory processor initialized")
            
        # Initialize summary scheduler
        if 'summary_scheduler' not in st.session_state or not st.session_state.summary_scheduler:
            st.session_state.summary_scheduler = SummaryScheduler(
                st.session_state.api_key, 
                st.session_state.db,
                st.session_state.memory_processor
            )
            st.session_state.summary_scheduler.start()
            logger.info("Summary scheduler initialized and started")

def on_shutdown():
    """Stop background processes on application shutdown"""
    if 'summary_scheduler' in st.session_state and st.session_state.summary_scheduler:
        st.session_state.summary_scheduler.stop()
        logger.info("Summary scheduler stopped on shutdown")

def initialize_context_manager():
    """Initialize the context manager if it doesn't exist in session state"""
    if 'context_manager' not in st.session_state and 'api_key' in st.session_state and st.session_state.api_key:
        st.session_state.context_manager = ContextManager(st.session_state.api_key)
        logger.info("Context manager initialized")



def get_enhanced_ai_response(prompt, model="gpt-4o-mini"):
    """
    Enhanced version of get_ai_response that uses the context manager
    for better context understanding and personalization.
    
    Args:
        prompt: The user's message
        model: The model to use
        
    Returns:
        The AI's response
    """
    if not st.session_state.api_key:
        return "Please add your OpenAI API key in the settings to use the AI coach."
    
    try:
        # Initialize context manager if needed
        initialize_context_manager()
               
        # Get response using context manager
        logger.info(f"Getting enhanced AI response using {model}")
        response = st.session_state.context_manager.get_ai_response(
            st.session_state.user_id,
            prompt,
            model
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in get_enhanced_ai_response: {str(e)}", exc_info=True)
        return f"Error communicating with AI service: {str(e)}"


# Replace profile loading function
def load_profile(name, passphrase):
    try:
        user_id = st.session_state.db.authenticate_user(name, passphrase)
        if user_id:
            # Clear existing session state
            st.session_state.clear()
            
            # Reinitialize database
            st.session_state.db = DatabaseManager()
            
            # Get profile from database
            profile = st.session_state.db.get_user_profile(user_id)
            
            # Update session state with profile data
            st.session_state.user_id = user_id
            st.session_state.name = profile['name']
            st.session_state.coach_name = profile['coach_name']
            st.session_state.coach_vibes = profile['coach_vibes']
            st.session_state.custom_instructions = profile['custom_instructions']
            st.session_state.codex_vitae = profile['codex_vitae']
            st.session_state.selected_model = profile['selected_model']
            
            # Load conversation history from database
            st.session_state.conversation_history = st.session_state.db.get_conversation_history(user_id)
            
            return True, "Profile loaded successfully!"
        return False, "Incorrect name or passphrase."
    except Exception as e:
        return False, f"Error loading profile: {str(e)}"

# Create sidebar sections
st.sidebar.markdown("## Navigation")
navigation = st.sidebar.radio(
    "Go to:",
    ["1. Vibe Engineering", 
     "2. Create Your Codex Vitae", 
     "3. Chat with Your Coach"],
    index=st.session_state.step - 1
)

# Set step based on navigation
st.session_state.step = int(navigation[0])

# Settings section in sidebar
st.sidebar.markdown("---")
with st.sidebar.expander("Configure AI Settings"):
    # API key input
    api_key = st.text_input("OpenAI API key:", type="password", key="sidebar_api_key")
    if api_key:
        st.session_state.api_key = api_key
        st.session_state.openai_client = openai.OpenAI(api_key=api_key)
        initialize_memory_services() 
        
    # Model selection
    selected_model = st.selectbox(
        "AI Model:",
        ["gpt-4o-mini", "gpt-4o "],
        key="sidebar_model"
    )
    if selected_model != st.session_state.selected_model:
        st.session_state.selected_model = selected_model
        st.success("Model updated!")

st.sidebar.markdown("---")

   

with st.sidebar.expander("🧠 Memory Management"):
    st.markdown("### Conversation Memory")
    
    tabs = st.tabs(["Summaries", "Generate", "Manage"])
    
    with tabs[0]:  # Summaries
        summary_type = st.radio("Summary Type:", ["Daily", "Weekly"])
        timeframe = summary_type.lower()
        
        if st.button("Refresh Summary"):
            summary = st.session_state.db.get_latest_summary(
                st.session_state.user_id, timeframe
            )
            st.session_state.current_summary = summary
        
        # Get current summary
        if 'current_summary' not in st.session_state:
            summary = st.session_state.db.get_latest_summary(
                st.session_state.user_id, timeframe
            )
            st.session_state.current_summary = summary
        else:
            summary = st.session_state.current_summary
        
        if summary and 'summary' in summary:
            summary_data = summary["summary"]
            st.markdown(f"*Last updated: {summary.get('last_updated', 'unknown')}*")
            
            # Display summary data if available
            for field in ["key_themes", "emotional_journey", "insights_gained", 
                         "progress_made", "action_items", "recommended_focus"]:
                if field in summary_data and summary_data[field]:
                    # Format field name for display
                    display_name = field.replace('_', ' ').title()
                    st.markdown(f"**{display_name}:**")
                    
                    # Different display based on field type
                    if isinstance(summary_data[field], list):
                        for item in summary_data[field]:
                            st.markdown(f"• {item}")
                    else:
                        st.markdown(summary_data[field])
                    
                    st.markdown("---")
        else:
            st.info(f"No {timeframe} summary available yet.")
    
    with tabs[1]:  # Generate Summaries
        st.markdown("Generate summaries manually:")
        
        summary_type_gen = st.radio("Summary to Generate:", ["Daily", "Weekly"], key="gen_summary_type")
        if st.button("Generate Summary Now"):
            if not st.session_state.api_key:
                st.error("Please add your OpenAI API key in the settings to generate summaries.")
            else:
                timeframe = summary_type_gen.lower()
                
                # Make sure memory processor is initialized
                if 'memory_processor' not in st.session_state or not st.session_state.memory_processor:
                    st.session_state.memory_processor = MemoryProcessor(st.session_state.api_key, st.session_state.db)
                
                # Generate the summary
                with st.spinner(f"Generating {timeframe} summary..."):
                    try:
                        st.session_state.memory_processor.generate_timeframe_summary(
                            st.session_state.user_id, timeframe
                        )
                        
                        # Update current summary in session state
                        summary = st.session_state.db.get_latest_summary(
                            st.session_state.user_id, timeframe
                        )
                        st.session_state.current_summary = summary
                        
                        st.success(f"{summary_type_gen} summary generated!")
                    except Exception as e:
                        st.error(f"Error generating summary: {str(e)}")
    
    with tabs[2]:  # Manage Memory
        st.markdown("Manage conversation memory:")
        
        # Clear recent conversations
        if st.button("Clear Recent Conversations"):
            st.session_state.conversation_history = []
            st.success("Recent conversations cleared!")
            
st.sidebar.markdown("---")

with st.sidebar.expander("⚠️ Danger Zone"):
    if st.button("Clear Database", type="primary"):
        confirm = st.button("⚠️ Confirm Clear Database")
        if confirm:
            st.session_state.db.reset_database()
            # Reset session state
            for key in list(st.session_state.keys()):
                if key != 'db':
                    del st.session_state[key]
            st.success("Database cleared successfully!")
            st.rerun()

# Register the shutdown handler
# In Streamlit, we can't directly register shutdown handlers
# But we can check for session resets
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
else:
    # If the script is rerun but initialized is already set, 
    # we might need to restart background processes
    if 'summary_scheduler' in st.session_state and st.session_state.summary_scheduler:
        if not hasattr(st.session_state.summary_scheduler, 'thread') or not st.session_state.summary_scheduler.thread.is_alive():
            logger.info("Restarting summary scheduler after session refresh")
            st.session_state.summary_scheduler.start()

# Main content
def main():
    # Landing page with profile creation/loading
    if not st.session_state.user_id:
        st.markdown('<div class="main-header">Welcome to Your Wellness AI Coach</div>', unsafe_allow_html=True)
        
        # Create tabs for new profile and existing profile
        login_tab, create_tab = st.tabs(["Load Existing Profile", "Create New Profile"])
        
        with login_tab:
            st.markdown("### Load Your Profile")
            name = st.text_input("Your Name:", key="login_name")
            passphrase = st.text_input("Your Passphrase:", type="password", key="login_passphrase")
            
            if st.button("Load Profile"):
                if name and passphrase:
                    success, message = load_profile(name, passphrase)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please enter both name and passphrase.")
        
        with create_tab:
            st.markdown("### Create New Profile")
            new_name = st.text_input("Your Name:", key="create_name")
            new_passphrase = st.text_input("Create Passphrase:", type="password", key="create_passphrase")
            confirm_passphrase = st.text_input("Confirm Passphrase:", type="password", key="confirm_passphrase")
            
            if st.button("Create Profile"):
                if new_name and new_passphrase and confirm_passphrase:
                    if new_passphrase == confirm_passphrase:
                        # Create the user in the database first
                        user_id = st.session_state.db.create_user(new_name, new_passphrase)
                        
                        # Clear all relevant session state variables
                        st.session_state.clear()
                        
                        # Reinitialize essential variables
                        st.session_state.db = DatabaseManager()
                        st.session_state.user_id = user_id
                        st.session_state.name = new_name
                        st.session_state.passphrase = new_passphrase
                        st.session_state.coach_name = ""
                        st.session_state.coach_vibes = ""
                        st.session_state.custom_instructions = ""
                        st.session_state.codex_vitae = {}
                        st.session_state.selected_model = "gpt-4o-mini"
                        st.session_state.conversation_history = []
                        
                        st.success("Profile created successfully!")
                        st.rerun()
                    else:
                        st.error("Passphrases do not match.")
                else:
                    st.warning("Please fill in all fields.")

    # If user is logged in, show the main app content
    if st.session_state.user_id:
        if st.session_state.step == 1:
            st.markdown('<div class="main-header">⚡ Build Your Own Nervous System AI Coach</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-header">#1: Vibe Engineering</div>', unsafe_allow_html=True)
            
            st.markdown("""<div class="highlight-box">
Fill in the blanks in this template to create your personalized AI coach.
</div>""", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                coach_name = st.text_input(
                    "Enter your coach's name:",
                    value=st.session_state.coach_name,
                    key="coach_name_input",
                    on_change=lambda: st.session_state.update({'template_initialized': False})
                )
                if coach_name:
                    st.session_state.coach_name = coach_name
                
                coach_vibes = st.text_input(
                    "Enter your coach's vibes (e.g. warm, playful, direct):",
                    value=st.session_state.coach_vibes,
                    key="coach_vibes_input",
                    on_change=lambda: st.session_state.update({'template_initialized': False})
                )
                if coach_vibes:
                    st.session_state.coach_vibes = coach_vibes
            
            with col2:
                st.image("https://img.freepik.com/free-vector/brain-with-digital-circuit-lines-artificial-intelligence_107791-11305.jpg", 
                         caption="Your AI Nervous System Coach", 
                         width=300)
            
            # Initialize or update the template
            if not st.session_state.template_initialized:
                st.session_state.custom_instructions = get_default_instructions()
                st.session_state.template_initialized = True

            st.markdown("### Custom Instructions Template")
            custom_instructions = st.text_area(
                "Edit your custom instructions template:",
                value=st.session_state.custom_instructions,
                height=400,
                key="custom_instructions_area"
            )

            # Update custom instructions if changed
            if custom_instructions != st.session_state.custom_instructions:
                st.session_state.custom_instructions = custom_instructions
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Changes"):
                    st.session_state.db.update_user_profile(
                        st.session_state.user_id,
                        st.session_state.name,
                        coach_name,
                        coach_vibes,
                        custom_instructions,
                        st.session_state.selected_model
                    )
                    st.success("Changes saved successfully!")
            with col2:
                if st.button("Continue to Step 2"):
                    st.session_state.step = 2
                    st.rerun()

        elif st.session_state.step == 2:
            st.markdown('<div class="main-header">⚡ Build Your Own Nervous System AI Coach</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-header">#2: Create Your Nervous System Codex Vitae</div>', unsafe_allow_html=True)
            
            st.markdown("""<div class="highlight-box">
Your Codex Vitae (Book of Life) serves as a detailed context about yourself and your nervous system tendencies. 
Select questions that resonate with you and answer them one by one to build your personalized document.
</div>""", unsafe_allow_html=True)
            
            # List of questions with emojis
            questions = {
                "core_values": "☄ Core Values + Direction: What are your 3-5 core values, mission statement or guiding questions to live into?",
                "theme_for_year": "🍂 Theme for this Year: What season of life are you in right now? What is the priority or theme for this particular chapter?",
                "permission_to_challenge": "💥 Permission to challenge: To what degree are you open to fierce or confronting constructive feedback? What is your (genuine) preference here?",
                "ideal_weekly_calendar": "📆 Ideal weekly calendar: How many hrs/day you like to devote to creative or business tasks vs. family or self-care. What does any ideal average week look like to you?",
                "ongoing_accountability": "💪 Ongoing accountability: What are some of your most important success scaffolding? Who are some of the people who you can lean on when things get challenging?",
                "energetic_black_holes": "🕳 Energetic black holes: Are there any known 'rabbit holes' where you lose hours or get stuck & how often do these happen and what typically triggers them?",
                "reactivity_triggers": "🖤 Reactivity triggers: What are 2-3 scenarios or moments when you have historically fallen into a more reactive mode of being?",
                "self_regulation_strategies": "🫁 Self-regulation strategies: What are some specific self-regulation or co-regulation strategies for moments when you notice that you're feeling overwhelm or need to downshift?",
                "burnout_warning_signs": "🔥 Burnout warning signs: If you've experienced burnout or sustained overwhelm in the past, what were some of the early warning signs?",
                "joy_triggers": "💙 Joy triggers: What reliably lights you up or triggers joy?",
                "emotional_processing": "😭 Emotional processing: When intense emotions or triggers arise, what typically helps you to move through, feel and express them?",
                "fear_inventory": "😬 Fear inventory: List 3-5 of your top fears and what is your typical coping style?",
                "decision_making_principles": "🙋‍♂️ Decision making principles: What are some of your personal decision making principles that keep you in integrity with yourself and others?",
                "ongoing_edges": "🏔 Ongoing edges: Specify key skills, challenges or areas you're actively working on that bring you to the edge of your capacity or ability?",
                "biomarkers_biometrics": "👨‍🔬 Biomarkers + biometrics: Any relevant biomarkers that need work as well as your resting average baseline HRV(or other health metrics that matter to you)",
                "prior_experiment_results": "🧪 Prior experiment results: What self-experimentation have you explored in the past that you would either like to repeat or do less of in the future?"
            }
            
            # Display question selector
            selected_question = st.selectbox("Select a question to answer:", list(questions.values()))
            
            # Get the key for the selected question
            selected_key = list(questions.keys())[list(questions.values()).index(selected_question)]
            
            # Display text area for answer
            answer = st.text_area("Your answer:", value=st.session_state.codex_vitae.get(selected_key, ""), height=200)
            
            # Save answer to session state
            if st.button("Save Answer"):
                st.session_state.db.update_codex_vitae(
                    user_id=st.session_state.user_id,
                    question_key=selected_key,
                    answer=answer
                )
                st.success(f"Answer saved for: {selected_question}")
                
                # Update the session state to reflect the change
                st.session_state.codex_vitae = st.session_state.db.get_user_profile(
                    st.session_state.user_id
                )['codex_vitae']
            
            # Preview Codex Vitae
            st.markdown('<div class="subsection-header">Preview Your Codex Vitae</div>', unsafe_allow_html=True)
            
            if st.session_state.codex_vitae:
                with st.expander("View Your Codex Vitae", expanded=True):
                    # Create two columns for each entry
                    for key, value in list(st.session_state.codex_vitae.items()):  # Convert to list to avoid runtime modification issues
                        if value:  # Only show if there's an answer
                            col1, col2 = st.columns([0.9, 0.1])  # 90% for content, 10% for delete button
                            with col1:
                                st.markdown(f"**{questions[key]}**")
                                st.markdown(value)
                            with col2:
                                # Add delete button for each entry
                                if st.button("🗑️", key=f"delete_{key}"):
                                    st.session_state.db.delete_codex_vitae_entry(
                                        user_id=st.session_state.user_id,
                                        question_key=key
                                    )
                                    # Update session state
                                    st.session_state.codex_vitae = st.session_state.db.get_user_profile(
                                        st.session_state.user_id
                                    )['codex_vitae']
                                    st.rerun()
                            st.markdown("---")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Back to Step 1"):
                    st.session_state.step = 1
                    st.rerun()
            with col2:
                if st.button("Continue to Step 3"):
                    st.session_state.step = 3
                    st.rerun()

        elif st.session_state.step == 3:
            st.markdown('<div class="main-header">⚡ Build Your Own Nervous System AI Coach</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-header">#3: Chat with Your Coach</div>', unsafe_allow_html=True)
            
            # Create container for the entire content
            main_container = st.container()
            
            # Create two columns with fixed widths
            with main_container:
                left_col, right_col = st.columns([0.4, 0.6], gap="large")
                
                # Left column - Prompt Library
                with left_col:
                    st.markdown("### Prompt Library")
                    tabs = st.tabs(["Nervous System", "Additional"])
                    
                    with tabs[0]:  # Nervous System Prompts tab
                        st.markdown("#### Pre-made Nervous System Prompts")
                        for key, prompt in NERVOUS_SYSTEM_PROMPTS.items():
                            with st.expander(f"{prompt['emoji']} {prompt['title']}"):
                                st.markdown(prompt['text'])
                                if st.button("Use Prompt", key=f"use_{key}"):
                                    st.session_state.current_input = prompt['text']
                                    st.rerun()

                    with tabs[1]:  # Additional Prompts tab
                        st.markdown("#### Additional Coaching Prompts")
                        for key, prompt in ADDITIONAL_PROMPTS.items():
                            with st.expander(f"{prompt['emoji']} {prompt['title']}"):
                                st.markdown(prompt['text'])
                                if st.button("Use Prompt", key=f"use_additional_{key}"):
                                    st.session_state.current_input = prompt['text']
                                    st.rerun()

                # Right column - Chat Interface
                with right_col:
                    st.markdown("### Chat with Your Coach")
                    st.markdown("""<div class="highlight-box">
                    Chat with your AI coach using your own messages or the prompt library.
                    </div>""", unsafe_allow_html=True)
                    
                    # Create a container for the entire chat interface
                    chat_interface = st.container()
                    
                    with chat_interface:
                        # Messages container
                        st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
                        if st.session_state.user_id:
                            conversation_history = st.session_state.db.get_conversation_history(st.session_state.user_id)
                            if conversation_history:
                                for msg in conversation_history:
                                    role_emoji = "👤" if msg["role"] == "user" else "🤖"
                                    with st.chat_message(msg["role"], avatar=role_emoji):
                                        st.markdown(msg["content"])
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Chat input area
                        st.markdown('<div class="chat-input-area">', unsafe_allow_html=True)
                        if 'current_input' not in st.session_state:
                            st.session_state.current_input = ""
                            
                        cols = st.columns([0.92, 0.08])
                        with cols[0]:
                            user_input = st.text_area(
                                "Type your message here...",
                                value=st.session_state.current_input,
                                height=100,
                                key="chat_input",
                                label_visibility="collapsed"
                            )
                        with cols[1]:
                            send_button = st.button("↑", key="send_button", use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    if send_button and user_input:
                        if not st.session_state.api_key:
                            st.error("Please add your OpenAI API key in the settings to use the AI coach.")
                        else:
                            message_to_send = user_input
                            st.session_state.current_input = ""
                            
                            try:
                                # First check if this exact message exists in recent history
                                recent_messages = st.session_state.db.get_conversation_history(st.session_state.user_id)[-5:]
                                is_duplicate = any(
                                    msg['role'] == "user" and 
                                    msg['content'] == message_to_send and 
                                    (datetime.fromisoformat(msg.get('timestamp', datetime.now().isoformat())) > datetime.now() - timedelta(minutes=1))
                                    for msg in recent_messages
                                )
                                
                                if not is_duplicate:
                                    # Save user message to database
                                    message_id = st.session_state.db.save_conversation(
                                        st.session_state.user_id, 
                                        "user", 
                                        message_to_send
                                    )
                                    
                                    # Get AI response
                                    response = get_enhanced_ai_response(message_to_send)
                                    
                                    # Save AI response to database
                                    st.session_state.db.save_conversation(
                                        st.session_state.user_id, 
                                        "assistant", 
                                        response
                                    )
                                    
                                    # Force a rerun to refresh the chat display
                                    st.rerun()
                                else:
                                    st.warning("Duplicate message detected - not processing")
                            except Exception as e:
                                st.error(f"Error processing message: {str(e)}")

if __name__ == "__main__":
    main()