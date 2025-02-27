css = """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #4B0082;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.8rem;
        font-weight: bold;
        color: #6A0DAD;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .subsection-header {
        font-size: 1.4rem;
        font-weight: bold;
        color: #8A2BE2;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    .highlight-box {
        background-color: #F8F8FF;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #8A2BE2;
    }
    .emoji-bullet {
        font-size: 1.2rem;
        margin-right: 0.5rem;
    }
    /* Style for chat input */
    [data-testid="stChatInput"] {
        height: 150px !important;
    }
    
    [data-testid="stChatInput"] > div {
        height: 150px !important;
    }
    
    [data-testid="stChatInput"] textarea {
        height: 150px !important;
        max-height: 150px !important;
    }
    
    /* Style for send button container */
    .stButton {
        margin-top: 25px;  /* Align with text area */
    }
    
    /* Make text area take full width */
    .stTextArea textarea {
        width: 100%;
    }
    
    /* Chat container styles */
    .chat-container {
        height: 400px;
        overflow-y: auto;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #ffffff;
    }
    
    /* Custom scrollbar styling */
    .chat-container::-webkit-scrollbar {
        width: 8px;
    }
    
    .chat-container::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    .chat-container::-webkit-scrollbar-thumb {
        background: #8A2BE2;
        border-radius: 10px;
    }
    
    .chat-container::-webkit-scrollbar-thumb:hover {
        background: #6A0DAD;
    }
</style>
"""
