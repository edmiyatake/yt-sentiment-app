import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    youtube_api_base_url: str = "https://www.googleapis.com/youtube/v3"
    youtube_api_key: str | None = os.getenv("YOUTUBE_API_KEY")


settings = Settings()