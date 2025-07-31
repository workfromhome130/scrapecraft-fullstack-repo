from langchain_openai import ChatOpenAI
from app.config import settings

def get_llm():
    """Get the OpenRouter LLM instance configured for Kimi-k2."""
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        temperature=0.7,
        streaming=True,
        default_headers={
            "HTTP-Referer": "https://scrapecraft.app",
            "X-Title": "ScrapeCraft"
        }
    )