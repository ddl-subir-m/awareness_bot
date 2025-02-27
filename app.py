import streamlit as st
import json
import os
import uuid
import openai
from pathlib import Path
from prompts import NERVOUS_SYSTEM_PROMPTS, ADDITIONAL_PROMPTS, DEFAULT_INSTRUCTIONS
from custom_css import css
from database import DatabaseManager
from memory_processor import MemoryProcessor

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

# Initialize database in session state
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()

# Initialize conversation history
st.session_state.conversation_history = []

# AI interaction functions
def get_ai_response(prompt, model="gpt-4o-mini"):
    if not st.session_state.api_key:
        return "Please add your OpenAI API key in the settings to use the AI coach."
    
    try:
        # Initialize OpenAI client if not already done
        if not st.session_state.openai_client:
            st.session_state.openai_client = openai.OpenAI(api_key=st.session_state.api_key)
        
        # Initialize memory processor
        memory_processor = MemoryProcessor(st.session_state.api_key, st.session_state.db)
        
        # Get relevant context
        context = memory_processor.get_relevant_context(prompt, st.session_state.user_id)
        
        messages = []
        
        # Add system instructions
        messages.append({
            "role": "system",
            "content": st.session_state.custom_instructions
        })
        
        # Add memory context if available
        if context:
            context_str = "Relevant context from our previous conversations:\n"
            for item in context.get("items", []):
                context_str += f"- {item['content']} (relevance: {item['relevance_score']}/10)\n"
            messages.append({
                "role": "system",
                "content": context_str
            })
        
        # Add recent conversation history
        for msg in st.session_state.conversation_history[-5:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add the current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Get response using the stored client
        response = st.session_state.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1500
        )
        
        # Process conversation for memory after getting response
        memory_processor.process_conversation(
            st.session_state.user_id,
            {"role": "user", "content": prompt}
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
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
     "2. Create Your Nervous System Codex Vitae", 
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

# Add to your sidebar section
with st.sidebar.expander("🧠 Memory Management"):
    st.markdown("### Conversation Memory")
    
    # View summaries
    if st.button("View Memory Summaries"):
        daily_summary = st.session_state.db.get_latest_summary(
            st.session_state.user_id, "daily"
        )
        weekly_summary = st.session_state.db.get_latest_summary(
            st.session_state.user_id, "weekly"
        )
        
        st.markdown("#### Daily Summary")
        st.json(daily_summary["summary"] if daily_summary else {})
        
        st.markdown("#### Weekly Summary")
        st.json(weekly_summary["summary"] if weekly_summary else {})
    
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


# Main content
def main():
    # Landing page with profile creation/loading
    if not st.session_state.user_id:
        st.markdown('<div class="main-header">Welcome to Your Nervous System AI Coach</div>', unsafe_allow_html=True)
        
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
            
            def get_default_instructions():
                return f"""Your name is {st.session_state.coach_name or '[coach_name]'}, and you are my Nervous System AI Coach.
                {DEFAULT_INSTRUCTIONS}"""

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
                    # Add a vertical divider using CSS
                    st.markdown("""
                        <style>
                        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"]:nth-of-type(2) {
                            border-left: 1px solid #ddd;
                            padding-left: 2rem;
                        }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("### Chat with Your Coach")
                    st.markdown("""<div class="highlight-box">
                    Chat with your AI coach using your own messages or the prompt library.
                    </div>""", unsafe_allow_html=True)
                    
                    # Display conversation history
                    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
                    chat_container = st.container()
                    with chat_container:
                        
                        # Only show messages if user is logged in and has conversation history
                        if st.session_state.user_id:
                            # Fetch fresh conversation history from database
                            conversation_history = st.session_state.db.get_conversation_history(st.session_state.user_id)
                            
                            # Add debug print to check database results
                            print(f"Database conversation history: {conversation_history}")
                            
                            # Only display messages if they exist in the database
                            if conversation_history:
                                for msg in conversation_history:
                                    role_emoji = "👤" if msg["role"] == "user" else "🤖"
                                    with st.chat_message(msg["role"], avatar=role_emoji):
                                        st.markdown(msg["content"])
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Chat input at the bottom
                    if 'current_input' not in st.session_state:
                        st.session_state.current_input = ""

                    # Create a container for the chat input and send button
                    input_container = st.container()
                    with input_container:
                        cols = st.columns([0.92, 0.08])  # Adjust ratio for better alignment
                        with cols[0]:
                            user_input = st.text_area(
                                "Type your message here...",
                                value=st.session_state.current_input,
                                height=100,
                                key="chat_input",
                                label_visibility="collapsed"  # Hide label for cleaner look
                            )
                        with cols[1]:
                            send_button = st.button("↑", key="send_button", use_container_width=True)

                    if send_button and user_input:
                        if not st.session_state.api_key:
                            st.error("Please add your OpenAI API key in the settings to use the AI coach.")
                        else:
                            message_to_send = user_input
                            st.session_state.current_input = ""
                            
                            try:
                                # Save user message to database
                                st.session_state.db.save_conversation(st.session_state.user_id, "user", message_to_send)
                                
                                # Get AI response
                                response = get_ai_response(message_to_send)
                                
                                # Save AI response to database
                                st.session_state.db.save_conversation(st.session_state.user_id, "assistant", response)
                                
                                # Force a rerun to refresh the chat display
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error processing message: {str(e)}")

if __name__ == "__main__":
    main()