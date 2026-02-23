import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "alexrap83@mail.ru")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./menu_bot.db")

# Payment
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN", "")
SUBSCRIPTION_PRICE_RUB = 299

# Limits
FREE_MAX_DAYS = 3
TRIAL_DAYS = 10
TRIAL_MAX_DAYS = 31

# Groq — актуальная модель
GROQ_MODEL = "llama-3.3-70b-versatile"
