"""Install dummy settings before the application is imported.

The FastAPI app builds its settings, database engine, Chroma client, and CrewAI
agents at import time. Tests never call OpenAI, Tavily, Postgres, or Chroma.
These values are placeholders so importing the app does not require a developer
.env file or a real API key. Existing environment variables win, which is what
CI uses.
"""

import os

_DEFAULTS = {
    "APP_NAME": "DocuCrew",
    "APP_ENV": "test",
    "DEBUG": "false",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "SECRET_KEY": "test-secret-key-for-tests-only",
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
    "SALT_ROUNDS": "4",
    "OPENAI_API_KEY": "sk-test-key-not-used-in-tests",
    "OPENAI_MODEL": "gpt-4o-mini",
    "EMBEDDING_MODEL": "text-embedding-3-small",
    "TAVILY_API_KEY": "tvly-test-key-not-used-in-tests",
    "CHROMA_PERSIST_DIR": "/tmp/docucrew-chroma-tests",
    "REDIS_URL": "redis://localhost:6379",
    "CREWAI_DISABLE_TELEMETRY": "true",
    "OTEL_SDK_DISABLED": "true",
}

for _key, _value in _DEFAULTS.items():
    os.environ.setdefault(_key, _value)

ENV_READY = True
