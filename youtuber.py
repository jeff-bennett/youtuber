from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc
import dateparser
from datetime import datetime
import timeago
import time
import os
import codecs
import re
import json
import sys
from rich import print
from bs4 import BeautifulSoup
from glob import glob
from dotenv import load_dotenv

import streamlit as st
from streamlitextras.webutils import stxs_javascript
from typing import NoReturn
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from pytubefix import YouTube, Channel
from openai import OpenAI

# set this to True to skip the youtube home page reload
# use this if the import crashes and you don't want to reload the youtube home page
SKIP_RELOAD = False

# Load environment variables from .env file
load_dotenv()

# Required environment variables
REQUIRED_ENV_VARS = [
    'MODEL', 'MAX_TOKENS', 'OPENAI_API_KEY', 'YOUTUBE_USERNAME',
    'YOUTUBE_PASSWORD', 'ALLOW_ANY_CATEGORY',
    'CATEGORIES',
    'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST'
]

# Validate environment variables
missing_or_blank = []
for var in REQUIRED_ENV_VARS:
    value = os.getenv(var)
    if value is None or value.strip() == '':
        missing_or_blank.append(var)

if missing_or_blank:
    print(f"[red]Error: The following environment variables are missing or blank in .env file:[/red]")
    for var in missing_or_blank:
        print(f"[red]  - {var}[/red]")
    print("[red]Please ensure all required variables are set in your .env file.[/red]")
    sys.exit(1)

MODEL = os.getenv('MODEL')
MAX_TOKENS = int(os.getenv('MAX_TOKENS'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

YOUTUBE_USERNAME = os.getenv('YOUTUBE_USERNAME')
YOUTUBE_PASSWORD = os.getenv('YOUTUBE_PASSWORD')


def get_chromium_version():
    """Detect Chromium/Chrome major version from the installed browser executable."""
    try:
        chrome_path = uc.find_chrome_executable()
        if not chrome_path:
            return None
        result = subprocess.run(
            [chrome_path, '--version'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        # Output format: "Google Chrome 144.0.1234.56" or "Chromium 144.0.1234.56"
        match = re.search(r'(\d+)\.', result.stdout.strip())
        return int(match.group(1)) if match else None
    except Exception:
        return None

# Starting list of categories (from .env). The AI will use this and may add more if ALLOW_ANY_CATEGORY is True.
CATEGORIES = {c.strip() for c in os.getenv('CATEGORIES').split(',') if c.strip()}

# set this to True to allow the AI to invent new categories
ALLOW_ANY_CATEGORY = os.getenv('ALLOW_ANY_CATEGORY', 'False').lower() in ('true', '1', 'yes')

POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')

#############################################

st.set_page_config(layout="wide")

@st.cache_resource
def get_app_variables():
    return {}

def view_homepage():
    st.title('YouTuber')
    cur.execute('SELECT category, count(*) FROM videos WHERE category IS NOT NULL AND NOT HIDDEN GROUP BY category ORDER BY category')
    result = cur.fetchall()
    categories = [row[0] for row in result]

    labels = {}
    for row in result:
        labels[row[0]] = f'{row[0]} ({row[1]})'
    now = datetime.now()

    category = st.selectbox('Category: ', categories, key='category', format_func=lambda x: labels[x])
    if category != 'All':
        where = "AND category = %s"
        params = (category,)
    else:
        where = ''
        params = ()

    named_cur.execute(f'SELECT * FROM videos WHERE HIDDEN = FALSE {where} ORDER BY id DESC LIMIT 50', params)
    video_list = named_cur.fetchall()

    col1, col1a, col2, col3, col4, col5, col6 = st.columns([1, 1, 4, 2, 1, 1, 1])
    col1.write('Thumbnail  \nChannel')
    col1a.write('Category')
    col2.write('Title')
    col3.write('Length  \nCreated')
    col4.write('Progress')
    col5.write('Hide')
    col6.write('Link')
    first = True
    for video in video_list:
        with st.container(border=True):
            col1, col1a, col2, col3, col4, col5, col6 = st.columns([1, 1, 4, 2, 1, 1, 1])
            if video['thumbnail']:
                col1.image(video['thumbnail'])
            col1.write(video['channel'])
            col1a.write(video['category'])
            col2.markdown(f"**{video['title']}**")
            if video['subtitles']:
                col2_1, col2_2, col2_3, col2_4 = col2.columns([1, 1, 1, 1])
                if col2_1.checkbox('Subs', key='subs-'+str(video['id'])):
                    st.html(f'<span style="font-size: 1.2rem">{video["subtitles"]}</span>')
    #             if col2_2.checkbox('Blurb', key='blurb-'+str(video['id'])):
    #                 st.warning(video['blurb'])
                if not first and col2_2.checkbox('Sum', key='summary-'+str(video['id'])):
                    st.html(f'<span style="font-size: 1.2rem">{video["summary"]}</span>')
    #             if col2_4.checkbox('Thm', key='themes-'+str(video['id'])):
    #                 st.warning(video['themes'])
                if col2_3.button('Retry', key='retry-summary-'+str(video['id'])):
                    summary = get_summary(video['subtitles'], MAX_TOKENS)
                    st.write(summary)
                    cur.execute('UPDATE videos SET summary = %s WHERE id = %s', (summary, video['id']))
                    conn.commit()
            if video['video_length']:
                col3.write(video['video_length'])
            if video['video_created']:
                col3.write(timeago.format(video['video_created'], now))
            col4.write(str(video['progress']))
            col5.checkbox('hidden', value=video['hidden'], key='hidden-'+str(video['id']), on_change=on_change_checkbox, args=(video['id'],), label_visibility='hidden')
            col6.write('[link](%s)' % video['link'])
            if first:
                st.html(f'<span style="font-size: 1.2rem">{video["summary"]}</span>')
                first = False

    st.markdown('<a href="/?action=import" target="_self">Import New Videos</a>', unsafe_allow_html=True)
    st.markdown('<a href="/?action=categories" target="_self">Manage Categories</a>', unsafe_allow_html=True)

# Matches PostgreSQL-style duration: M:SS or H:MM:SS (e.g. "5:30", "1:23:45")
_VALID_VIDEO_LENGTH = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')


def normalize_video_length_for_interval(value):
    """Return value if it's a valid interval string (M:SS or H:MM:SS), else '00:00'."""
    if value is None:
        return None
    s = value.strip() if isinstance(value, str) else str(value).strip()
    if s and _VALID_VIDEO_LENGTH.match(s):
        return s
    return '00:00'


def import_home_page():
    st.markdown('<a href="/" target="_self">Home</a>', unsafe_allow_html=True)

    if 'driver' in app_variables:
        print('reloading driver state from session')
        driver = app_variables['driver']
        conn.rollback()
        if not SKIP_RELOAD:
            driver.get('https://www.youtube.com/')
    else:
        chrome_kwargs = {'headless': False, 'use_subprocess': False, 'version_main': get_chromium_version()}
        driver = uc.Chrome(**chrome_kwargs)
        app_variables['driver'] = driver

        # Navigate to YouTube
        driver.get('https://www.youtube.com/')
        time.sleep(5)
        sign_in_button = driver.find_element(By.XPATH, '//*[@id="buttons"]/ytd-button-renderer/yt-button-shape/a')
        sign_in_button.click()
        time.sleep(2)
        email_input = driver.find_element(By.XPATH, '//input[@type="email"]')
        email_input.send_keys(YOUTUBE_USERNAME)
        email_input.send_keys(Keys.RETURN)
        time.sleep(2)
        password_input = driver.find_element(By.XPATH, '//input[@type="password"]')
        password_input.send_keys(YOUTUBE_PASSWORD)
        password_input.send_keys(Keys.RETURN)
        time.sleep(15)  # Wait for the homepage to load

    if not SKIP_RELOAD:
        # Scroll to the bottom of the page
        last_height = driver.execute_script("return document.documentElement.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        try:
            show_more = driver.find_elements(By.XPATH, '//*[@id="dismissible"]/div[3]/ytd-button-renderer/yt-button-shape/button[@aria-label="Show more"]/yt-touch-feedback-shape/div/div[2]')
            driver.execute_script("arguments[0].click();", show_more[1])
        except:
            pass

        # Force lazy-loaded thumbnails to load by scrolling back up slowly
        st.write('Loading thumbnails...')
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        # Scroll down in chunks to trigger lazy loading
        scroll_height = driver.execute_script("return document.documentElement.scrollHeight")
        chunk_size = 800  # pixels per scroll
        for pos in range(0, scroll_height, chunk_size):
            driver.execute_script(f"window.scrollTo(0, {pos});")
            time.sleep(0.3)

    time.sleep(1)

    # Get page source and parse with BeautifulSoup
    html_content = driver.page_source

    # Optionally save for debugging
    # with codecs.open('youtube_home_page.html', "w", encoding='utf-8') as f:
    #     f.write(html_content)

    # Parse videos from HTML
    videos = parse_videos_from_html(html_content)
    st.write(f'Found {len(videos)} videos to process')

    for video_data in videos:
        st.write('--------------------------------')
        link = video_data['link']
        st.write(link)

        cur.execute("SELECT id FROM videos WHERE link = %s", (link,))
        result = cur.fetchone()

        if result:
            st.write('skipping already imported')
            continue

        title = video_data['title']
        st.write(title)

        channel = video_data['channel']
        thumbnail = video_data['thumbnail']
        progress = video_data['progress']
        video_length = normalize_video_length_for_interval(video_data['video_length'])
        created = video_data['created']

        summary = None
        blurb = None
        themes = None
        subtitles = None
        category = None

        try:
            yt = YouTube(link)
            subtitles = yt.captions.get('a.en', None)
            if subtitles:
                subtitles = sub_to_str(subtitles.json_captions)
                summary = get_summary(title + ' - ' + subtitles, MAX_TOKENS)
        except Exception as e:
            st.write(f'Error getting subtitles: {e}')

        if ALLOW_ANY_CATEGORY:
            category = get_category_raw(title, summary, themes)
        else:
            category = get_category(title, summary, themes)

        st.write(category)

        try:
            cur.execute("""INSERT INTO videos (title, link, channel, thumbnail, progress, video_created, video_length,
                                               subtitles, summary, blurb, themes, category) VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (title, link, channel, thumbnail, progress, created, video_length, subtitles,
                         summary, blurb, themes, category))
            conn.commit()
        except Exception as e:
            print(title, link, channel, thumbnail, progress, created, video_length, subtitles,
                     summary, blurb, themes, category)
            st.write(e)


    st.markdown('<a href="/" target="_self">Home</a>', unsafe_allow_html=True)

def import_subtitles():
    conn.rollback()
    named_cur.execute('SELECT * FROM videos WHERE HIDDEN = FALSE AND subtitles IS NULL ORDER BY id DESC limit 50')
    video_list = named_cur.fetchall()
    for video in video_list:
        st.write(video['link'])
        yt = YouTube(video['link'])
        yt.bypass_age_gate()
        subtitles = yt.captions.get('a.en', None)
        if subtitles:
            subtitles = sub_to_str(subtitles.json_captions)
            cur.execute('UPDATE videos SET subtitles = %s WHERE id = %s', (subtitles, video['id']))
            conn.commit()

def import_themes():
    conn.rollback()
    named_cur.execute('SELECT * FROM videos WHERE HIDDEN = FALSE AND themes IS NULL')
    video_list = named_cur.fetchall()
    for video in video_list:
        st.write(video['link'])
        blurb = None
#         blurb = get_blurb(video['title'] + ' - ' + video['subtitles'], 1024)
#         st.write(blurb)
        themes = get_themes(video['title'] + ' - ' + video['subtitles'], 1024)
        st.write(themes)
        category = get_category(video['title'], blurb, themes)
        st.write(category)
        st.write('-----------')

        cur.execute('UPDATE videos SET themes = %s, blurb = %s, category = %s WHERE id = %s', (themes, blurb, category, video['id']))
        conn.commit()

def categories():
    # get all categories
    st.markdown('<a href="/" target="_self">Home</a>', unsafe_allow_html=True)

    st.header('Categories')
    st.write('#### Enter a new category name to change the category of all videos in that category.')

    conn.rollback()
    cur.execute('SELECT DISTINCT(category) FROM videos WHERE category IS NOT NULL ORDER BY category')
    categories = cur.fetchall()
    # for each category, st.write category, st.input new category name

    for category in categories:
        col1, col2, col3 = st.columns([1,1,1])
        col1.write(category[0])
        new_category = col2.text_input('Rename category:', key = category[0], label_visibility="collapsed")
        if new_category:
            cur.execute('UPDATE videos SET category = %s WHERE category = %s', (new_category, category[0]))
            conn.commit()

    st.markdown('<a href="/" target="_self">Home</a>', unsafe_allow_html=True)

def get_category_raw(title, summary, themes, retries=0, previous=''):
    categories = CATEGORIES
    cur.execute("SELECT DISTINCT(category) FROM videos WHERE category IS NOT NULL and not category ilike 'Uncategorized'")

    for row in cur.fetchall():
        categories.add(row[0])
    categories = '\n'.join(list(categories))
    prompt = 'Example responses: ' + categories + '\n-------\n TITLE: ' + title
    if summary:
        prompt += '\n SUMMARY: ' + summary
    if themes:
        prompt += '\n THEMES: ' + themes
    if previous != '':
        prompt += '\n PREVIOUS BAD CATEGORIES: ' + previous

    category = prompt_all(prompt, 'Please very very carefully choose a category from this list for this video based on title '
                                  'and summary provided.  give a lot of extra thought to make sure that the category is '
                                  'appropriate because this is a very important task! If it is incorrect, someone will lose '
                                  'their job. only provide a category name from the list with no extra explanation or discussion. '
                                  'Return nothing except the category name because this output will be used by a dumb computer program!!! '
                                  'please think carefully before returning only a one or two word category name.', max_chunks=1).strip()
    category = category.replace('Category: ', '')
    # Extract text between ** if present
    if '**' in category:
        match = re.search(r'\*\*([^\*]+)\*\*', category)
        if match:
            category = match.group(1)
    print(f'=={category}==')
    cur.execute('SELECT 1 FROM videos WHERE category ilike %s limit 1', (category,))
    if (not cur.fetchone() or '"' in category or len(category.split()) > 3) and retries < 3:
        if len(category.split()) <= 3:
            if previous != '':
                previous = previous + ','
            previous = previous + category
        print(f'INVALID CATEGORY "{category}" Retrying')
        st.write(f'INVALID CATEGORY "{category}" Retrying')
        return get_category_raw(title, summary, themes, retries + 1, previous)

    # is_ok = prompt_all(prompt, f'The category "{category}" was chosen for this video based on the title and summary below.   Please let me know if you agree with the category chosen by answering only YES or NO with no additional explanation or discussion. Return nothing except "YES" or "NO" because this output will be used by a dumb computer program!!! please think carefully before returning only one single word: YES or NO.', max_chunks=1).strip()
    # print(f'~~{is_ok}~~')
    # if is_ok != 'YES' and retries < 3:
    #     if previous != '':
    #         previous = previous + ','
    #     previous = previous + category
    #     print(f'BAD CATEGORY "{category}" Retrying')
    #     st.write(f'BAD CATEGORY "{category}" Retrying')
    #     return get_category_raw(title, summary, themes, retries + 1, previous)

    if len(category.split()) > 3:
        category = 'Uncategorized'

    return category.replace('*','').replace('\n', '')

def get_category(title, summary, themes):
    categories = CATEGORIES
    cur.execute("SELECT DISTINCT(category) FROM videos WHERE category IS NOT NULL and not category ilike 'Uncategorized'")

    for row in cur.fetchall():
        categories.add(row[0])

    llm = OpenAI(api_key=OPENAI_API_KEY)

    categorize_tool = {
        "type": "function",
        "function": {
            "name": "categorize",
            "description": "Categorize a video based on title and summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string",
                                 "description": "The category to categorize the video into",
                                 "enum": list(CATEGORIES)},
                },
                "required": ["category"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    }

    category = None
    completion = llm.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": "You are an expert video categorizer. You are given a video title and summary and you need to select the best category for that video.",
        },{
            "role": "user",
            "content": f"Categorize the video '{title}' with the summary '{summary}'"
        },],
        tools=[categorize_tool],
    )
    completion.model_dump()

    if completion.choices[0].message.tool_calls:
        for tool_call in completion.choices[0].message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            category = args.get("category")

    print(f'=={category}==')

    return category

def sub_to_str(subtitles):
    string = ''
    if subtitles is None:
        return None
    for event in subtitles['events']:
        if 'segs' in event:
            for seg in event['segs']:
                string += seg['utf8']
    return string.replace('\n', ' ')


def parse_videos_from_html(html_content):
    """Parse video items from YouTube home page HTML using BeautifulSoup.

    Returns a list of dicts with video info: link, title, channel, thumbnail, progress, video_length, created
    """
    soup = BeautifulSoup(html_content, 'lxml')
    video_items = soup.find_all('ytd-rich-item-renderer')
    videos = []

    for video in video_items:
        # Skip ads
        if video.find('ytd-ad-slot-renderer'):
            continue

        # Skip sponsored content
        if video.find(string='Sponsored'):
            continue

        # Skip collections/stacks
        if video.find(class_='ytCollectionsStackCollectionStack2'):
            continue

        video_data = {}

        # Link - try the title link first, then content-image link
        link_elem = video.select_one('a.yt-lockup-metadata-view-model__title')
        if not link_elem:
            link_elem = video.select_one('a.yt-lockup-view-model__content-image')
        if not link_elem:
            link_elem = video.select_one('a#thumbnail')

        if link_elem:
            link = link_elem.get('href', '')
            if link and not link.startswith('http'):
                link = 'https://www.youtube.com' + link
            video_data['link'] = link.split('&')[0] if link else None
        else:
            continue  # Skip if no link found

        if not video_data.get('link'):
            continue

        # Title
        title_elem = video.select_one('h3.yt-lockup-metadata-view-model__heading-reset')
        if title_elem:
            video_data['title'] = title_elem.get('title') or title_elem.get_text(strip=True)
        else:
            continue  # Skip if no title

        # Channel
        channel_elem = video.select_one('.yt-content-metadata-view-model__metadata-row a')
        video_data['channel'] = channel_elem.get_text(strip=True) if channel_elem else None

        # Thumbnail
        thumb_elem = video.select_one('.ytThumbnailViewModelImage img')
        thumbnail = thumb_elem.get('src') if thumb_elem else None

        # Fallback: construct thumbnail URL from video ID if lazy-loading didn't populate it
        if not thumbnail and video_data['link']:
            video_id_match = re.search(r'[?&]v=([^&]+)', video_data['link'])
            if video_id_match:
                video_id = video_id_match.group(1)
                thumbnail = f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'

        video_data['thumbnail'] = thumbnail

        # Video length
        length_elem = video.select_one('yt-thumbnail-badge-view-model .yt-badge-shape__text')
        if length_elem:
            length_text = length_elem.get_text(strip=True)
            # Skip upcoming/live streams
            if length_text.upper() in ('UPCOMING', 'LIVE'):
                video_data['video_length'] = None
            else:
                video_data['video_length'] = length_text
        else:
            video_data['video_length'] = None

        # Progress (for partially watched videos)
        progress_elem = video.select_one('.ytThumbnailOverlayProgressBarHostWatchedProgressBarSegment')
        if progress_elem:
            style = progress_elem.get('style', '')
            # Extract percentage from "width: 61%;"
            match = re.search(r'width:\s*(\d+)%', style)
            video_data['progress'] = int(match.group(1)) if match else 0
        else:
            video_data['progress'] = 0

        # Views and created date from metadata rows
        metadata_rows = video.select('.yt-content-metadata-view-model__metadata-row')
        video_data['created'] = None
        if len(metadata_rows) >= 2:
            spans = metadata_rows[1].select('span.yt-content-metadata-view-model__metadata-text')
            for span in spans:
                text = span.get_text(strip=True)
                # Look for time-based text (e.g., "2 hours ago", "1 month ago")
                if text and ('ago' in text or 'hour' in text or 'day' in text or 'week' in text or 'month' in text or 'year' in text):
                    video_data['created'] = dateparser.parse(text)
                    break

        videos.append(video_data)

    return videos

def summarize():
    conn.rollback()
    named_cur.execute('SELECT * FROM videos WHERE HIDDEN = FALSE AND subtitles IS NOT NULL AND summary IS NULL ORDER BY id DESC limit 50')
    video_list = named_cur.fetchall()
    for video in video_list:
        st.write(video['link'])
        summary = get_summary(video['subtitles'], MAX_TOKENS)
        blurb = None
        # blurb = get_blurb(video['subtitles'], 1024)
        themes = None
        # themes = get_themes(video['subtitles'], 1024)
        cur.execute('UPDATE videos SET summary = %s, blurb = %s, themes = %s WHERE id = %s', (summary, blurb, themes, video['id']))
        conn.commit()

def on_change_checkbox(id):
    # Select and print the URL from the video record
    cur.execute('SELECT link FROM videos WHERE id = %s', (id,))
    video_link = cur.fetchone()
    if video_link:
        print('Hiding: ' + video_link[0])

        cur.execute('update videos set hidden = %s where id = %s', (st.session_state['hidden-'+str(id)], id))
        conn.commit()

def get_themes(text, size=4096):
    themes = prompt_all(text[0:4096], "Return a brief list of major themes as bullet points: ")
    retries = 3
    while (len(themes) > size and retries >= 0):
        themes = prompt_all(themes, "Return a list of major themes as bullet points without repeating: ")
        retries -= 1

    return themes

def get_summary(text, size=4096):
    summary = prompt_all(text[0:4096], "Restate the following youtube video transcript in a few short sentences including whatever information in the transcript is alluded to by the title.  for example if the title says 'somebody said something crazy' or 'you will never believe what trump advisor did' then please include who it refers to and what they said or did and what effect it had.  do not include anything from the text that appears to be a commercial or an advertisement or product recommendation.  note that there may be incorrect words in the computer-generated transcript so do your best to correctly interpret the actual words - sometimes the title can help disambiguate.  there may be multiple speakers with different points of view so please try to separate those out.  !!!!DO NOT INCLUDE PRODUCT PLACEMENTS, COMMERICALS, ADVERTISEMENTS, PRODUCT RECOMMENDATIONS!!!!: ")
    retries = 3
    while (len(summary) > size and retries >= 0):
        summary = prompt_all(summary, "Restate the following summary of a youtube transcript in a more concise form.  do not include anything that appears to be an advertisement or product placement: ")
        retries -= 1

    return summary

def get_blurb(text, size=4096):
    return prompt_all(text[0:4096], "Turn this into a single short blurb: ")


################### OLLAMA ###################
# def prompt_all(text, prompt, model=MODEL, max_tokens=MAX_TOKENS, max_chunks=5):
#     texts = splitter.chunks(text)#, chunk_capacity=(MIN_TOKENS, max_tokens))
#     combined_texts = []
#     total_tokens = 0
#     current_text = ""

#     for text in texts:
#         text_tokens = len(encoding.encode(text))

#         if total_tokens + text_tokens <= MAX_TOKENS:
#             current_text += text
#             total_tokens += text_tokens
#         else:
#             combined_texts.append(current_text)
#             current_text = text
#             total_tokens = text_tokens

#     if current_text:
#         combined_texts.append(current_text)

#     output = ""
#     for combined_text in combined_texts[:max_chunks]:
#         prompt += str(combined_text)
#         # https://github.com/ollama/ollama/issues/2242
#         stream = ollama.generate(
#             model=model,
#             prompt=prompt,
#             stream=True
#         )
#         response = ''.join(chunk['response'] for chunk in stream).strip()
#         output += response + "\n"

#     output = re.sub(r"^Here( are| is|'s)\s.*?\n\n", '', output)
#     return output.strip()

################## OPENAI ###################
def prompt_all(text, prompt, model=MODEL, max_tokens=MAX_TOKENS, max_chunks=5):
    # Split the text into chunks that fit within the model's context window
    chunk_size = max_tokens // 2  # Adjust as needed
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    output = ""
    for chunk in chunks[:max_chunks]:
        full_prompt = prompt + chunk

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7,
            n=1,
            stop=None
        )

        output += response.choices[0].message.content + "\n"

    output = re.sub(r"^Here( are| is|'s)\s.*?\n\n", '', output)
    return output.strip()

#############################################

def create_pg_dump():
    today = datetime.now().strftime('%Y%m%d')
    dump_file_name = f'pg_dump_{today}.sql.gz'
    if os.path.exists(dump_file_name):
        return

    dump_files = glob('pg_dump_*.sql.gz')
    if len(dump_files) >= 5:
        oldest_dump = min(dump_files, key=os.path.getctime)
        os.remove(oldest_dump)

    print('creating backup', dump_file_name)
    os.system(f'pg_dump youtuber | gzip -9 > {dump_file_name}')
    print('finished creating backup')

def connect_to_postgres_db():
    conn = psycopg2.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST
    )
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS videos (
                   id SERIAL PRIMARY KEY,
                   title VARCHAR NOT NULL,
                   link VARCHAR NOT NULL,
                   channel VARCHAR,
                   thumbnail VARCHAR,
                   subtitles TEXT,
                   summary TEXT,
                   blurb TEXT,
                   themes TEXT,
                   progress INT,
                   category VARCHAR,
                   video_created TIMESTAMP,
                   video_length INTERVAL,
                   record_created TIMESTAMP NOT NULL DEFAULT NOW(),
                   hidden BOOLEAN NOT NULL DEFAULT FALSE
                   )""")

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS video_link ON videos (link)")
    conn.commit()
    named_cur = conn.cursor(cursor_factory=RealDictCursor)

    return conn, cur, named_cur

app_variables = get_app_variables()
if 'conn' in app_variables:
    print('reloading connection state from session')
    conn = app_variables['conn']
    cur = app_variables['cur']
    named_cur = app_variables['named_cur']
else:
    # Setup postgres
    conn, cur, named_cur = connect_to_postgres_db()
    app_variables['conn'] = conn
    app_variables['cur'] = cur
    app_variables['named_cur'] = named_cur

if __name__ == '__main__':
    create_pg_dump()

    action = None
    try:
        action = st.query_params['action']
    except KeyError:
        action = None

    match action:
        case 'import':
            import_home_page()
        case 'summarize':
            summarize()
        case 'subs':
            import_subtitles()
        case 'themes':
            import_themes()
        case 'categories':
            categories()
        case _:
            view_homepage()
