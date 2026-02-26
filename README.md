# YouTuber

A Streamlit-based web application for importing, categorizing, and managing YouTube videos from your personalized home page feed. Uses AI (OpenAI) to automatically summarize video transcripts and categorize videos.

**Note: This project is experimental.** Some functionality is currently commented out, including:
- Video blurb generation
- Theme extraction
- Ollama/local LLM support (code is present but disabled in favor of OpenAI)

## Features

- Import videos from your YouTube home page using Selenium automation
- Automatic subtitle/transcript extraction via pytubefix
- AI-powered video summarization using OpenAI
- Automatic video categorization (with optional free-form category generation)
- Category management interface
- Progress tracking for partially watched videos
- Hide videos you're not interested in
- Daily PostgreSQL database backups

## Prerequisites

- Python 3.10+
- PostgreSQL database
- Google Chrome or Chromium browser (for Selenium)
- OpenAI API key
- YouTube account credentials

## Setup

### 1. Clone the repository

```bash
cd /path/to/youtuber
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

You may also need to install `lxml` for HTML parsing:

```bash
pip install lxml
```

### 4. Set up PostgreSQL database

Create a PostgreSQL database for the application:

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create the database
CREATE DATABASE youtuber;

# Create a user (optional, if not using default postgres user)
CREATE USER youtuber_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE youtuber TO youtuber_user;

# Exit psql
\q
```

The application will automatically create the required `videos` table on first run.

### 5. Configure environment variables

Copy the sample environment file and edit it with your credentials:

```bash
cp .env.sample .env
```

Edit `.env` with your settings:

| Variable | Description |
|----------|-------------|
| `MODEL` | OpenAI model to use (e.g., `gpt-4o-mini`) |
| `MAX_TOKENS` | Maximum tokens for AI responses (e.g., `8192`) |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `YOUTUBE_USERNAME` | Your YouTube/Google account email |
| `YOUTUBE_PASSWORD` | Your YouTube/Google account password |
| `ALLOW_ANY_CATEGORY` | `True` to let AI create new categories, `False` to stop generating new categories and only use those plus the `CATEGORIES` list |
| `CATEGORIES` | Comma-separated list of predefined categories |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_HOST` | PostgreSQL host (e.g., `localhost`) |
| `SERVER_PORT` | Port for Streamlit server (default: `7086`) |

## Usage

### Starting the server

```bash
./start.sh
```

Or manually:

```bash
source venv/bin/activate
streamlit run youtuber.py --server.port 7086
```

The application will be available at `http://localhost:7086`

### Main Pages

#### Home Page (`/`)

The main view displays your imported videos organized by category:
- Select a category from the dropdown to filter videos
- View video thumbnails, titles, channels, and lengths
- Click "Subs" to view the video transcript
- Click "Sum" to view the AI-generated summary
- Click "Retry" to regenerate a summary
- Check "hidden" to hide videos from the list
- Click the link to open the video on YouTube

#### Import Videos (`/?action=import`)

Imports videos from your YouTube home page:
1. Opens a Chrome browser window
2. Logs into your YouTube account (first run only)
3. Scrolls through your home page to load videos
4. Extracts video metadata (title, channel, thumbnail, etc.)
5. Fetches subtitles/transcripts where available
6. Generates AI summaries
7. Auto-categorizes each video

**Note:** The first import requires manual login. You may need to complete 2FA or CAPTCHA challenges in the browser window.

#### Manage Categories (`/?action=categories`)

Rename or merge categories:
- View all existing categories
- Enter a new name to rename a category (all videos in that category will be updated)

### Additional Actions (URL parameters)

- `/?action=summarize` - Generate summaries for videos that have subtitles but no summary
- `/?action=subs` - Import subtitles for videos missing them
- `/?action=themes` - Extract themes from videos (functionality partially commented out)

### Configuration Options

In `youtuber.py`, you can modify:

- `SKIP_RELOAD = True` - Set to skip reloading the YouTube home page during import (useful if the import crashes and you want to resume without re-scraping)

## Database Schema

The `videos` table contains:

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `title` | VARCHAR | Video title |
| `link` | VARCHAR | YouTube video URL |
| `channel` | VARCHAR | Channel name |
| `thumbnail` | VARCHAR | Thumbnail URL |
| `subtitles` | TEXT | Video transcript |
| `summary` | TEXT | AI-generated summary |
| `blurb` | TEXT | Short blurb (currently unused) |
| `themes` | TEXT | Extracted themes (currently unused) |
| `progress` | INT | Watch progress percentage |
| `category` | VARCHAR | Video category |
| `video_created` | TIMESTAMP | When video was published |
| `video_length` | INTERVAL | Video duration |
| `record_created` | TIMESTAMP | When record was imported |
| `hidden` | BOOLEAN | Whether video is hidden from view |

## Backups

The application automatically creates daily PostgreSQL backups on startup:
- Backup files are named `pg_dump_YYYYMMDD.sql.gz`
- Only the 5 most recent backups are kept

## Troubleshooting

- **Chrome/Selenium issues**: Ensure Chrome/Chromium is installed and accessible. The app auto-detects the browser version.
- **Login failures**: YouTube may require CAPTCHA or 2FA. Complete these manually in the browser window.
- **Import crashes**: Set `SKIP_RELOAD = True` in `youtuber.py` to resume without re-fetching the home page.

## License

This project is for personal use.
