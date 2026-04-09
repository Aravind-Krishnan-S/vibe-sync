import os
import json
import re
import tiktoken
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

CONTEXT_FILENAME = "VIBE_CONTEXT.md"
HISTORY_LOG_FILE = ".vibe/history_log.json"

def count_tokens(text: str) -> int:
    """Monitor the size of text using tiktoken."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def compress_history(file_path: str = CONTEXT_FILENAME):
    if not os.path.exists(file_path):
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # The user rule states: "If the file exceeds 2,000 tokens"
    if count_tokens(content) <= 2000:
        return

    # Look for "Warm Path" section. We fallback to "Current Progress" if Warm Path isn't found.
    section_regex = r"(##\s+(?:Warm Path|Current Progress|🚦 Current Progress)[\s\S]*?)(?=\n##\s|\Z)"
    match = re.search(section_regex, content, re.IGNORECASE)
    
    if not match:
        return
        
    old_section_full = match.group(1)
    
    # Extract the heading and the body
    lines = old_section_full.split("\n", 1)
    heading = lines[0] if len(lines) > 0 else "## Warm Path"
    old_detailed_logs = lines[1] if len(lines) > 1 else ""
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found. Skipping compression.")
        return
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    
    prompt = (
        "Summarize these 20 development steps into 5 high-level architectural milestones.\n\n"
        f"Input Logs:\n{old_detailed_logs}"
    )
    
    try:
        response = model.generate_content(prompt)
        milestones_summary = response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini for compression: {e}")
        return

    # Move raw detailed logs to hidden history_log.json for manual reference
    os.makedirs(os.path.dirname(HISTORY_LOG_FILE), exist_ok=True)
    history = []
    if os.path.exists(HISTORY_LOG_FILE):
        try:
            with open(HISTORY_LOG_FILE, "r", encoding="utf-8") as hf:
                history = json.load(hf)
        except json.JSONDecodeError:
            pass
            
    history.append({
        "original_logs": old_detailed_logs,
        "milestones_summary": milestones_summary
    })
    
    with open(HISTORY_LOG_FILE, "w", encoding="utf-8") as hf:
        json.dump(history, hf, indent=4)
        
    # Replace the old detailed logs with this new "Milestones" summary
    new_section = f"{heading}\n\n### Milestones\n{milestones_summary}\n"
    new_content = content.replace(old_section_full, new_section)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print(f"Compressed history. Raw logs appended to {HISTORY_LOG_FILE}")
