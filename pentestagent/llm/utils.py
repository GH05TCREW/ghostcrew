"""LLM utility functions for PentestAgent."""

from typing import List, Optional


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text.

    Args:
        text: The text to count
        model: The model (used to select tokenizer)

    Returns:
        Token count
    """
    try:
        import tiktoken

        # Select encoding based on model
        if "gpt-4" in model or "gpt-3.5" in model:
            encoding = tiktoken.get_encoding("cl100k_base")
        else:
            encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(text))

    except ImportError:
        # Fallback approximation
        return int(len(text.split()) * 1.3)


def truncate_to_tokens(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    """
    Truncate text to a maximum number of tokens.

    Args:
        text: The text to truncate
        max_tokens: Maximum tokens
        model: The model (used to select tokenizer)

    Returns:
        Truncated text
    """
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)

    except ImportError:
        # Fallback approximation
        words = text.split()
        target_words = int(max_tokens / 1.3)
        return " ".join(words[:target_words])


def estimate_tokens(text: str) -> int:
    """
    Quick estimation of token count without loading tokenizer.

    Args:
        text: The text to estimate

    Returns:
        Estimated token count
    """
    # Average: ~4 characters per token for English
    return len(text) // 4


def format_messages_for_display(messages: List[dict], max_length: int = 500) -> str:
    """
    Format messages for display (e.g., in logs).

    Args:
        messages: Messages to format
        max_length: Maximum length per message

    Returns:
        Formatted string
    """
    lines = []

    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")

        if len(content) > max_length:
            content = content[:max_length] + "..."

        lines.append(f"[{role}] {content}")

    return "\n".join(lines)


def extract_code_blocks(text: str) -> List[dict]:
    """
    Extract code blocks from markdown text.

    Args:
        text: Text containing code blocks

    Returns:
        List of dicts with 'language' and 'code' keys
    """
    import re

    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    return [
        {"language": lang or "text", "code": code.strip()} for lang, code in matches
    ]


def extract_tool_calls_from_text(text: str) -> List[dict]:
    """
    Extract tool call references from text (for display purposes).

    Args:
        text: Text that may contain tool references

    Returns:
        List of potential tool calls
    """
    import re

    # Look for patterns like "use tool_name" or "call tool_name"
    pattern = r"(?:use|call|execute|run)\s+(\w+)"
    matches = re.findall(pattern, text.lower())

    return [{"tool": match} for match in matches]


def sanitize_for_shell(text: str) -> str:
    """
    Sanitize text for safe shell usage.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    # Escape dangerous characters
    dangerous = ["`", "$", "\\", '"', "'", ";", "&", "|", ">", "<", "\n", "\r"]

    result = text
    for char in dangerous:
        result = result.replace(char, f"\\{char}")

    return result


def parse_llm_json(text: str) -> Optional[dict]:
    """
    Attempt to parse JSON from LLM output.

    Args:
        text: Text that may contain JSON

    Returns:
        Parsed dict or None
    """
    import json
    import re

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in code blocks
    pattern = r"```(?:json)?\n?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try to find JSON object in text
    pattern = r"\{[^{}]*\}"
    matches = re.findall(pattern, text)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    return None
