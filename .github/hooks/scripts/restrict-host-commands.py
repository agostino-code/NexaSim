import sys
import json

def main():
    try:
        # Read the hook input from stdin
        input_data = json.load(sys.stdin)
        
        tool_name = input_data.get("toolName", "")
        
        # Check if the tool is a terminal execution tool
        # (This covers standard Copilot and Claude terminal tool names)
        terminal_tools = [
            "run_in_terminal", 
            "default_api:run_in_terminal"
        ]
        
        if tool_name in terminal_tools:
            tool_input = input_data.get("toolInput", {})
            command = tool_input.get("command", "").strip()
            
            # If a command is provided and it doesn't invoke Docker, block it
            if command and not command.startswith("docker"):
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Command '{command}' is not using docker. All build and Conan operations MUST run inside the artery-dev container (e.g., docker exec -it artery-dev bash -c \"...\")."
                    },
                    "systemMessage": "Please wrap your command in a docker exec call targeting the artery-dev container."
                }
                print(json.dumps(output))
                sys.exit(0)
                
    except Exception as e:
        # If parsing fails, fall back to allowing to avoid breaking the agent
        pass
        
    # Default case: allow the tool usage
    print(json.dumps({
        "hookSpecificOutput": {
             "hookEventName": "PreToolUse",
             "permissionDecision": "allow"
        }
    }))
    sys.exit(0)

if __name__ == "__main__":
    main()