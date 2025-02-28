import logging
import os
import json
from datetime import datetime

def setup_logging(log_level=logging.DEBUG):
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('nervous_system_coach')
    logger.setLevel(log_level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create console handler with a higher log level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create file handler for detailed logging
    log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(log_level)
    
    # Create formatters
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Add formatters to handlers
    console_handler.setFormatter(console_formatter)
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def format_llm_messages(messages, truncate_length=1000):
    """Format messages for logging, with optional truncation for very long content"""
    formatted = []
    for idx, msg in enumerate(messages):
        content = msg.get('content', '')
        # Truncate very long content for readability but indicate original length
        if content and len(content) > truncate_length:
            original_length = len(content)
            content = content[:truncate_length] + f"... [truncated, full length: {original_length} chars]"
        
        formatted.append({
            "index": idx,
            "role": msg.get('role', 'unknown'),
            "content": content
        })
    return formatted

def log_llm_request(logger, model, messages, temperature=None, max_tokens=None, other_params=None):
    """Log details of requests to LLM models"""
    # Format the basic request info
    request_info = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "type": "LLM_REQUEST"
    }
    
    # Add any other parameters
    if other_params:
        request_info.update(other_params)
    
    # Log the request metadata
    logger.info(f"LLM REQUEST: {json.dumps(request_info)}")
    
    # Log the messages in a readable format
    formatted_messages = format_llm_messages(messages)
    for msg in formatted_messages:
        logger.info(f"LLM MESSAGE {msg['index']} - {msg['role']}: {msg['content']}")
    
    # Add a separator for readability
    logger.info("-" * 80)

def log_llm_response(logger, response_text, model=None, tokens_used=None):
    """Log the response from LLM models"""
    llm_logger = logger.getChild('llm')
    
    # Log metadata if available
    metadata = {}
    if model:
        metadata["model"] = model
    if tokens_used:
        metadata["tokens_used"] = tokens_used
    
    if metadata:
        llm_logger.info(f"LLM RESPONSE METADATA: {json.dumps(metadata)}")
    
    # Truncate very long responses for log readability
    if len(response_text) > 1000:
        original_length = len(response_text)
        truncated = response_text[:1000] + f"... [truncated, full length: {original_length} chars]"
        llm_logger.info(f"LLM RESPONSE (truncated): {truncated}")
    else:
        llm_logger.info(f"LLM RESPONSE: {response_text}")
    
    # Add a separator for readability
    llm_logger.info("=" * 80)

def log_structured_output_request(logger, model, messages, response_format_class, temperature=0.7):
    """
    Log LLM requests that use structured output
    
    Args:
        logger: The logger instance
        model: The model being used
        messages: The messages being sent
        response_format_class: The response format class
        temperature: Temperature setting (default 0.7)
    """
    # Format response_format info
    format_info = {
        "type": "structured_output",
        "class": response_format_class.__name__ if hasattr(response_format_class, "__name__") else str(response_format_class)
    }
    
    # Log the request using the existing function
    log_llm_request(
        logger,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=None,
        other_params={"response_format": format_info}
    )

def log_structured_output_response(logger, model, parsed_response):
    """
    Log responses from structured output LLM calls
    
    Args:
        logger: The logger instance
        model: The model being used
        parsed_response: The parsed response
    """
    # Convert to string representation for logging
    if hasattr(parsed_response, "model_dump"):
        response_text = str(parsed_response.model_dump())
    elif hasattr(parsed_response, "dict"):
        response_text = str(parsed_response.dict())
    else:
        response_text = str(parsed_response)
    
    # Log the response using the existing function
    log_llm_response(
        logger,
        response_text=response_text,
        model=model
    )