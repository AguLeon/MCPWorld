import json

def _normalize_tool_call(tool_name: str, tool_input: dict) -> str:
    """
    Create a normalized string representation of a tool call for comparison.
    This helps detect repeated tool calls even if there are minor variations.
    """
    if tool_name == "computer":
        action = tool_input.get("action", "")
        coordinate = tool_input.get("coordinate")
        text = tool_input.get("text", "")
        scroll_direction = tool_input.get("scroll_direction", "")
        
        # Normalize coordinate to avoid minor pixel differences
        if coordinate and isinstance(coordinate, list) and len(coordinate) == 2:
            # Round to nearest 10 pixels to catch "similar" clicks
            coord_normalized = (round(coordinate[0] / 10) * 10, round(coordinate[1] / 10) * 10)
        else:
            coord_normalized = None
        
        return json.dumps({
            "tool": tool_name,
            "action": action,
            "coordinate": coord_normalized,
            "text": text[:50] if text else "",
            "scroll": scroll_direction,
        }, sort_keys=True)
    
    elif tool_name == "bash":
        command = tool_input.get("command", "")
        return json.dumps({
            "tool": tool_name,
            "command": command[:100],
        }, sort_keys=True)
    
    elif tool_name == "str_replace_editor":
        return json.dumps({
            "tool": tool_name,
            "path": tool_input.get("path", ""),
            "command": tool_input.get("command", ""),
        }, sort_keys=True)
    
    else:
        input_str = json.dumps(tool_input, sort_keys=True)
        if len(input_str) > 200:
            input_str = input_str[:200]
        return json.dumps({
            "tool": tool_name,
            "input": input_str,
        }, sort_keys=True)


def _detect_tool_call_loop(
    recent_tool_calls: list[str],
    max_repeated: int = 3,
) -> tuple[bool, str]:
    """
    Detect if the agent is stuck in a loop by checking for repeated tool calls.

    Returns:
        tuple: (is_loop_detected, loop_description)
    """
    if len(recent_tool_calls) < max_repeated:
        return False, ""

    # Check for exact repetition of the last tool call
    last_call = recent_tool_calls[-1]
    consecutive_count = 1
    for i in range(len(recent_tool_calls) - 2, -1, -1):
        if recent_tool_calls[i] == last_call:
            consecutive_count += 1
        else:
            break

    if consecutive_count >= max_repeated:
        try:
            call_data = json.loads(last_call)
            tool_name = call_data.get("tool", "unknown")
            return True, f"Detected {consecutive_count} consecutive identical calls to '{tool_name}' tool"
        except:
            return True, f"Detected {consecutive_count} consecutive identical tool calls"

    # Check for alternating pattern (A-B-A-B-A-B)
    if len(recent_tool_calls) >= 6:
        if (recent_tool_calls[-1] == recent_tool_calls[-3] == recent_tool_calls[-5] and
            recent_tool_calls[-2] == recent_tool_calls[-4] == recent_tool_calls[-6]):
            return True, "Detected alternating pattern of two tool calls repeated 3+ times"

    return False, ""
