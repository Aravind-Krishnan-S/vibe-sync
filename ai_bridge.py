import os
import re
import sys

import google.generativeai as genai
from dotenv import load_dotenv

from config import load_config

load_dotenv()


class MissingAPIKeyError(Exception):
    """Raised when the GEMINI_API_KEY environment variable is not set."""


def _get_api_key() -> str:
    """Return the Gemini API key or raise if missing."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise MissingAPIKeyError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )
    return key


def _strip_code_fences(text: str) -> str:
    """Remove markdown code-block wrappers (```markdown ... ```) if present."""
    stripped = re.sub(
        r"^```(?:markdown|md)?\s*\n(.*?)```\s*$",
        r"\1",
        text.strip(),
        flags=re.DOTALL,
    )
    return stripped.strip()


SYSTEM_PROMPT = (
    "You are an expert AI developer tracking project state. "
    "Your job is to rewrite a project context document so it accurately "
    "reflects the latest code changes. Keep the exact same heading structure. "
    "Focus on updating 'Current Progress' and 'The Next Move'. "
    "Return ONLY the raw markdown content — no surrounding code fences."
)


def _call_ai_studio(user_prompt: str) -> str:
    """Core AI Studio logic (Gemini API). 
    Used as the primary engine and fallback for Vertex failures.
    """
    # Ensure we don't accidentally trigger Vertex AI logic in genai library
    gcp_project_backup = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if "GOOGLE_CLOUD_PROJECT" in os.environ:
        del os.environ["GOOGLE_CLOUD_PROJECT"]

    api_key = _get_api_key()
    genai.configure(api_key=api_key)

    # Try a robust set of models with and without prefixes
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-2.0-flash-exp",
        "models/gemini-1.5-flash",
        "models/gemini-2.0-flash",
    ]

    last_err = None
    for name in models_to_try:
        try:
            model = genai.GenerativeModel(
                model_name=name,
                system_instruction=SYSTEM_PROMPT,
            )
            response = model.generate_content(user_prompt)
            
            if gcp_project_backup:
                os.environ["GOOGLE_CLOUD_PROJECT"] = gcp_project_backup
                
            return _strip_code_fences(response.text)
        except Exception as e:
            last_err = e
            continue
    
    if gcp_project_backup:
        os.environ["GOOGLE_CLOUD_PROJECT"] = gcp_project_backup
        
    print(f"⚠️ [AI Studio Warning]: Core engine failed ({last_err}). Falling back to Groq...")
    try:
        return _call_groq_api(user_prompt)
    except Exception as groq_err:
        print(f"⚠️ [Groq Warning]: Groq fallback failed ({groq_err}). Falling back to NVIDIA NIM...")
        try:
            return _call_nvidia_nim(user_prompt)
        except Exception as nvidia_err:
            raise Exception(
                f"All AI engines exhausted.\n"
                f"  Gemini: {last_err}\n"
                f"  Groq:   {groq_err}\n"
                f"  NVIDIA:  {nvidia_err}"
            )

def _call_groq_api(user_prompt: str) -> str:
    """Final fallback to Groq API using Llama 3 to avoid total failure."""
    try:
        import groq
    except ImportError:
        raise Exception("groq package not installed")
        
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise Exception("GROQ_API_KEY missing - unable to fallback")

    # Workaround: newer httpx versions reject 'proxies' kwarg passed by older groq SDK
    try:
        client = groq.Groq(api_key=api_key)
    except TypeError:
        import httpx
        http_client = httpx.Client()
        client = groq.Groq(api_key=api_key, http_client=http_client)
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.5
    )
    return _strip_code_fences(chat_completion.choices[0].message.content)


def _call_nvidia_nim(user_prompt: str) -> str:
    """Final fallback to NVIDIA NIM free API (OpenAI-compatible).
    Uses meta/llama-3.3-70b-instruct on build.nvidia.com.
    Requires NVIDIA_API_KEY (starts with 'nvapi-') in .env.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise Exception("openai package not installed — run: pip install openai")

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise Exception("NVIDIA_API_KEY missing — get one free at https://build.nvidia.com")

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        max_tokens=4096,
    )
    return _strip_code_fences(response.choices[0].message.content)


def update_context_via_ai(current_context: str, git_diff: str) -> str:
    """Send the current context and recent changes to Gemini and return
    an updated VIBE_CONTEXT.md body.
    """
    user_prompt = (
        f"Here is the current VIBE_CONTEXT.md:\n\n"
        f"{current_context}\n\n"
        f"---\n\n"
        f"Here are the latest code changes:\n\n"
        f"{git_diff}\n\n"
        f"---\n\n"
        f"Rewrite the VIBE_CONTEXT.md to accurately reflect the new progress, "
        f"keeping the exact same heading structure. "
        f"Focus on updating 'Current Progress' and 'The Next Move'."
    )

    # Resolve project ID for Vertex AI fallback
    config = load_config()
    use_vertex = str(os.getenv("USE_VERTEX_AI", "")).lower() == "true"

    if use_vertex:
        # ─── VERTEX AI (ENTERPRISE / GCP CREDITS) ───
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            
            gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT") or config.get("google_project_id")
            vertexai.init(project=gcp_project)
            model = GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                system_instruction=[SYSTEM_PROMPT]
            )
            response = model.generate_content(user_prompt)
            return _strip_code_fences(response.text)
        except Exception as e:
            # NON-BLOCKING FALLBACK: Log a warning and use AI Studio
            print(f"⚠️ [Vertex AI Warning]: Performance engine failed ({e}). Falling back to Core AI Studio...")
            return _call_ai_studio(user_prompt)

    else:
        # ─── CORE AI STUDIO (GEMINI API) ───
        return _call_ai_studio(user_prompt)
