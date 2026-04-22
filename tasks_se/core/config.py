from pathlib import Path
import os
from dotenv import load_dotenv


load_dotenv()
CHROME_VERSION = os.getenv("CHROME_VERSION")
print(f"CHROME_VERSION: {CHROME_VERSION}")

CONFIG_PATH = Path(__file__).resolve()
CORE_DIR = CONFIG_PATH.parent
LOG_DIR = os.path.join(CORE_DIR.parent, "logs")
print(f"LOG_DIR: {LOG_DIR}")

