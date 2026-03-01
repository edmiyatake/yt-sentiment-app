# YouTube Sentiment Analyzer

A small web app that analyzes YouTube video comments and highlights overall sentiment trends.

Users can paste a YouTube video URL, select a random sample size, and view:

* **Positive / Neutral / Negative** sentiment percentages
* **Recurring themes** in comments
* **Specific theme details** (for example, what part of the game users describe as creative)
* A per-comment explanation of why each comment was labeled the way it was

## Features

* Analyze a random sample of **50, 100, or 200** comments
* Fetch comments from the **YouTube Data API**
* Use an **LLM** to classify sentiment and identify recurring feedback themes
* Show both **broad themes** and **specific areas** within those themes
* Cache comment pools in memory for faster repeated analysis on the same video

## Tech Stack

* **Backend:** FastAPI
* **Frontend:** HTML, CSS, JavaScript
* **APIs:** YouTube Data API, OpenAI API

## Getting Started

### 1. Install dependencies

```bash
python -m pip install fastapi "uvicorn[standard]" requests python-dotenv openai
```

### 2. Create a `.env` file

```env
YOUTUBE_API_KEY=your_youtube_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 3. Run the app

```bash
uvicorn app.main:app --reload
```

### 4. Open in browser

Go to:

```text
http://127.0.0.1:8000/app
```

## Project Structure

```text
app/
├── core/
├── models/
├── services/
└── main.py

static/
├── css/
├── js/
└── index.html
```

## Notes

* This project uses **in-memory caching**, so cached data resets when the server restarts.
* The analysis is based on a **random sample** of fetched comments, not necessarily every comment on the video.

## Future Improvements

* Add clickable theme filters
* Save past analyses
* Improve category depth and custom theme taxonomies
* Add charts and visualizations
