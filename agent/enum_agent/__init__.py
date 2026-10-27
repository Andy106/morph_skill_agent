from pathlib import Path

from dotenv import load_dotenv

# Load agent/.env (OPENAI_API_KEY, OPENAI_MODEL, ENUM_API_URL) before any submodule reads the environment.
# Variables already set in the shell take precedence over the file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
