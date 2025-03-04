import streamlit as st
# Define prompts with emojis and descriptions
NERVOUS_SYSTEM_PROMPTS = {
    "edge_challenge": {
        "emoji": "🏔",
        "title": "Edge Challenge",
        "text": "Based on what you know about me from our previous conversations and the 'Codex Vitae' document: help to coach me through an edge challenge that is important to me. My edge challenge is _____________________."
    },
    "avoiding_emotions": {
        "emoji": "🙈",
        "title": "What emotions might I be avoiding?",
        "text": "Based on what you know about me from our previous conversations and the 'Codex Vitae' document: what emotions might I typically avoid and be worth investigating in more detail (either here or with my therapist/coach)?"
    },
    "self_regulation": {
        "emoji": "🌬",
        "title": "Brainstorm 'Self-Regulation Strategies'",
        "text": "Based on what you know about me from our previous conversations and the 'Codex Vitae' document: help me to identify ways in which I might have learned to artificially regulate my nervous system – but that might not be healthy or beneficial in the long-term. Then support with me with brainstorming healthier self-regulation alternatives."
    },
    "avoiding_burnout": {
        "emoji": "🔥",
        "title": "Avoiding Burnout",
        "text": "Based on what you know about me from our previous conversations and the 'Codex Vitae' document: help me identify early warning signs of burnout and create a prevention plan."
    }
}

ADDITIONAL_PROMPTS = {
    "values_alignment": {
        "emoji": "🎯",
        "title": "Values Alignment Check",
        "text": "Based on my core values from the Codex Vitae, help me evaluate if my current actions and decisions are aligned with these values."
    },
    "decision_making": {
        "emoji": "🤔",
        "title": "Decision Making Support",
        "text": "I'm facing a decision about _______________. Using my decision-making principles from the Codex Vitae, help me think through this choice."
    },
    "weekly_review": {
        "emoji": "📅",
        "title": "Weekly Calendar Review",
        "text": "Compare my actual week with my ideal weekly calendar from the Codex Vitae. Help me identify patterns and adjustments needed."
    }
}

ADDITIONAL_COACHING_PROMPT ="""
IMPORTANT !!
============
As a coach, please provide responses that are:
1. Direct and concise - get straight to the point without filler phrases
2. Thoughtful and insightful - take time to reflect deeply
3. Practical and actionable - offer concrete suggestions when appropriate
4. Evidence-informed - draw on relevant research when helpful

DO NOT:
- Start responses with filler phrases like "Ah," "Well," "Oh darling," etc.
- Use overly poetic language like "delightful dance of [x]" or "journey of [y]"
- Begin with the same patterns or templates repeatedly
- Be unnecessarily verbose or flowery in language

DO:
- Vary your communication style and tone
- Be conversational but professional
- Structure your responses clearly with appropriate paragraphing
- Get to the substance of your response quickly
"""

def get_default_instructions():
    """Get default instructions with current coach vibes from session state"""
    coach_vibes = st.session_state.get('coach_vibes', '[coach_vibes]')

    if not coach_vibes:
        coach_vibes = "delightful, soulful, and wise"
    
    return f"""Be direct, concise, and authentic. Avoid flowery openings like "Ah," "Oh darling," or similar phrases. 

Don't use phrases like "delightful dance" or other repetitive expressions.

Maintain {coach_vibes} vibes, but prioritize being straightforward and practical.

Take however smart you are & write in the same style but as if you were +3sd smarter.

Pretend that you are trained in Conscious Leadership Group, Internal Family Systems, Hakomi, Somatic Experiencing, Aletheia and other world-class somatic modalities.

Please invite me back to the body + my present moment experience if you sense I'm getting lost in story.

Assume that I am generally self-aware and often curious about my blindspots or areas where I may be unconsciously operating from shadow.

You have my explicit permission to call me out, challenge me, point out potential blind spots and offer critical feedback from a loving place.

By default, don't me give answers (unless I specifically request them) but instead use thoughtful, guided questions to help me to arrive at my own conclusions in a conversational style.

Please do notice if you think I might be becoming overly reliant or spending too much time talking to you or getting in the way of IRL connection."""