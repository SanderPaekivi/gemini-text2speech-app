import os
from dotenv import load_dotenv

load_dotenv()

# Authentication and Secrets
# NOTE: Swap to credentials file or .env file?
CREDENTIALS_FILE = "google-credentials.json"

# Set up authentication for the Google Cloud Text-to-Speech service
if os.path.exists(CREDENTIALS_FILE):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE
else:
    # If the file is not found or not set, raise an error to stop execution
    raise FileNotFoundError(
        f"Authentication Error: Credentials file not found at '{CREDENTIALS_FILE}'. "
        "Please ensure the GOOGLE_CREDENTIALS_FILE_PATH in your .env file is correct."
    )

# Pricing Configuration
# For Chirp 3: HD voices 
PRICE_PER_MILLION_CHARS_HD = 30.00  # USD per million characters: https://cloud.google.com/text-to-speech/pricing?hl=en
FREE_TIER_LIMIT = 1_000_000  # 1 million characters

# API and Processing Settings
# Maximum characters a single API request to Google TTS can be
TTS_CHUNK_SIZE = 4500
# For retry-mechanism
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # unit in seconds

# File Paths
TEXT_OUTPUT_FOLDER = "extracted texts"
AUDIO_OUTPUT_FOLDER = "generated audio"