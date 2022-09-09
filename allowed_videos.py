#!/usr/bin/env python3

import sys
import shlex
from pathlib import Path
from shutil import rmtree
from typing import NamedTuple, List, Dict
from datetime import timedelta
# noinspection PyUnresolvedReferences
from importlib import reload

import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2 import service_account
from isodate import parse_duration

PLAYLISTS = shlex.split("""
# To get the playlist ID of all uploads:
# Go to https://commentpicker.com/youtube-channel-id.php and get the channel ID.
# Replace the "UC" at the beginning with "UU".
# (It could also be done using the API, but this is easier)

# הקברניט
PLcv3NFnLaZVasCHfk6TUJ57_RM_BnlPHB

# פרפר נחמד העונות הראשונות
PL51YAgTlfPj7XTzORdSrWpgCfF1x7ZUeK

# גלילאו עונה 8 - פרקים מלאים
PL51YAgTlfPj57_dWdUXGLkf2pmCnYzYoF

# Griffpatch all uploads
UUawsI_mlmPA7Cfld-qZhBQA

# Numberblocks all uploads
UUPlwvN0w4qFSP1FllALB92w
""", comments=True)

MYDIR = Path(__file__).parent
# See https://stackoverflow.com/a/72815975/343036 for nice instructions on how to
# obtain this
KEY_JSON = MYDIR / 'youtube-upload-333607-779f879a1f2a.json'
BUILD_DIR = MYDIR / 'build'

credentials = service_account.Credentials.from_service_account_file(str(KEY_JSON))
youtube = googleapiclient.discovery.build(
    "youtube", "v3", credentials=credentials)


def execute(query):
    print(query.uri, file=sys.stderr)
    return query.execute()


def download_playlists_metadata():
    items = []
    page_token = None
    while True:
        r = execute(youtube.playlists().list(
            part="snippet",
            id=','.join(PLAYLISTS),
            maxResults=50,
            pageToken=page_token,
        ))
        items.extend(r['items'])
        if 'nextPageToken' not in r:
            break
        else:
            page_token = r['nextPageToken']
    return items


def download_playlist_items(playlist_id):
    items = []
    page_token = None
    while True:
        r = execute(youtube.playlistItems().list(
            part="id,snippet,contentDetails",
            maxResults=50,
            playlistId=playlist_id,
            pageToken=page_token,
        ))
        items.extend(r['items'])
        if 'nextPageToken' not in r:
            break
        else:
            page_token = r['nextPageToken']
    durations = download_durations([item['contentDetails']['videoId'] for item in items])
    for item in items:
        item['duration'] = durations[item['contentDetails']['videoId']]
    return items


def download_durations(video_ids: List[str]) -> Dict[str, timedelta]:
    chunk_size = 50
    chunks = [video_ids[i:i + chunk_size] for i in range(0, len(video_ids), chunk_size)]
    durations: Dict[str, timedelta] = {}
    for chunk in chunks:
        r = execute(youtube.videos().list(part='contentDetails', id=','.join(chunk)))
        for video_id, item in zip(chunk, r['items']):
            durations[video_id] = parse_duration(item['contentDetails']['duration'])
    return durations


def format_duration(td: timedelta):
    ts = int(td.total_seconds())
    tm, s = divmod(ts, 60)
    h, m = divmod(tm, 60)
    if h > 0:
        return f'{h}:{m:02}:{s:02}'
    else:
        return f'{m}:{s:02}'


def get_main_page(items):
    title = 'רשימות השמעה'
    item_datas: List[ItemData] = []
    for item in items:
        snippet = item['snippet']
        thumbnail = snippet['thumbnails']['medium']
        item_datas.append(ItemData(
            f'{item["id"]}.html',
            thumbnail['url'],
            thumbnail['width'],
            thumbnail['height'],
            snippet['title'],
        ))
    return get_list_page(title, item_datas)


def get_playlist_page(metadata, items):
    title = metadata['snippet']['title']
    item_datas: List[ItemData] = []
    for item in items:
        snippet = item['snippet']
        thumbnail = snippet['thumbnails']['medium']
        video_id = snippet["resourceId"]["videoId"]
        item_datas.append(ItemData(
            f'https://www.youtube.com/embed/{video_id}',
            thumbnail['url'],
            thumbnail['width'],
            thumbnail['height'],
            f'{snippet["title"]} ({format_duration(item["duration"])})',
        ))
    return get_list_page(title, item_datas)


class ItemData(NamedTuple):
    link_url: str
    img_url: str
    width: int
    height: int
    text: str


def get_list_page(title: str, items: List[ItemData]):
    s = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '  <head>\n'
        '    <meta charset="UTF-8">\n'
        f'    <title>{title}</title>\n'
        '    <style>\n'
        '      body {\n'
        '        font-family: Helvetica;\n'
        '      }\n'
        '      .container {\n'
        '        display: grid;\n'
        '        grid-template-columns: repeat(auto-fit, 340px);\n'
        '      }\n'
        '      .item {\n'
        '        padding: 10px;\n'
        '      }\n'
        '    </style>\n'
        '  </head>\n'
        '  <body dir="rtl">\n'
        f'    <div class="container">\n'
    )
    for item in items:
        s += (
            f'      <div class="item">\n'
            f'        <a href="{item.link_url}">\n'
            f'          <img loading="lazy" src="{item.img_url}" width="{item.width}" height="{item.height}">\n'
            f'        </a>\n'
            f'        <div class="title" dir="auto">{item.text}</div>\n'
            f'      </div>\n'
        )
    s += (
        '    </div>\n'
        '  </body>\n'
        '</html>\n'
    )
    return s


def download():
    playlists = download_playlists_metadata()
    playlist_items = []
    for playlist_id in PLAYLISTS:
        playlist_items.append(download_playlist_items(playlist_id))
    return playlists, playlist_items


def write_html(playlists, playlist_items):
    if BUILD_DIR.exists():
        rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()

    main_page = get_main_page(playlists)
    with open(BUILD_DIR / 'index.html', 'w') as f:
        f.write(main_page)
    for metadata, items in zip(playlists, playlist_items):
        playlist_id = metadata['id']
        playlist_page = get_playlist_page(metadata, items)
        with open(BUILD_DIR / f'{playlist_id}.html', 'w') as f:
            f.write(playlist_page)


def reimp():
    from inspect import currentframe

    cmd = "from importlib import reload; import allowed_videos; reload(allowed_videos); from allowed_videos import *"
    exec(cmd, currentframe().f_back.f_globals, currentframe().f_back.f_locals)


def main():
    playlists, playlist_items = download()
    write_html(playlists, playlist_items)


if __name__ == '__main__':
    main()