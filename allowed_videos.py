#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import shlex
from pathlib import Path
from shutil import rmtree
from typing import NamedTuple, List, Dict, Any, Tuple
from datetime import timedelta
# noinspection PyUnresolvedReferences
from importlib import reload
import json

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
# PL51YAgTlfPj7XTzORdSrWpgCfF1x7ZUeK

# אבודים בריבוע - פרקים מלאים
PL51YAgTlfPj4hZL5MM9K_Xk-ismQhYi-q

# אבודים בריבוע עונה 2 - פרקים מלאים
PL51YAgTlfPj7S1CFW1WdTS67RzyFrkyQn

# גלילאו עונה 8 - פרקים מלאים
PL51YAgTlfPj651bbZLZhS3JU_p-bIpGQc

# גלילאו עונה 9 - פרקים מלאים 
PL51YAgTlfPj57_dWdUXGLkf2pmCnYzYoF

# גלילאו עונה 10
PL51YAgTlfPj6vc696b-Pf-JOouxa7mCnv

# המתחם ה-25
PL51YAgTlfPj6MPmIl-qi1UeeIQLKx_Kpx

# שלי הכובשת
PL51YAgTlfPj724k2A8ssLug_Wux-3a_Q0

# Griffpatch all uploads
UUawsI_mlmPA7Cfld-qZhBQA

# Numberblocks all uploads
# UUPlwvN0w4qFSP1FllALB92w

# Colourblocks all uploads
# UUQkuKPaVlYK7QCIVTb0lV2Q

# Alphablocks all uploads
# UU_qs3c0ehDvZkbiEbOj6Drg

# @tdbricks all uploads
UUUU3GdGuQshZFRGnxAPBf_w

# Kurzgezagt
UUsXVk37bltHxD1rDPwtNM8Q

# Brick Science
UUpQB577lHFyWTyvrS73Ldlg

# Veritasium
UUHnyfMqiRRG1u-2MsSQLbXA

# 3blue1brown
UUYO_jab_esuFRV4b17AJtAw

# Mark Rober
UUY1kMZp36IQSyNx_9h4mpCg

# Nadav Nave
UUiGXQyV2DMEFyt1agByOQEA

# Everyday Astronaut
UU6uKrU_WqJ1R2HMTY3LIx5Q

# Stuff Made Here
UUj1VqrHhDte54oLgPG4xpuQ

# CGP Grey
UU2C_jShtL725hvbm1arSV9w
""", comments=True)

MYDIR = Path(__file__).parent
# See https://stackoverflow.com/a/72815975/343036 for nice instructions on how to
# obtain this
KEY_JSON = MYDIR / 'youtube-upload-333607-bab972dd5a7f.json'
BUILD_DIR = MYDIR / 'build'

if KEY_JSON.exists():
    key_data = json.load(open(KEY_JSON))
else:
    key_data = json.loads(os.environ['KEY_JSON'])
credentials = service_account.Credentials.from_service_account_info(key_data)
youtube = googleapiclient.discovery.build(
    "youtube", "v3", credentials=credentials)


StrDict = Dict[str, Any]


def execute(query: Any) -> StrDict:
    print(query.uri, file=sys.stderr)
    return query.execute()


def download_playlists_metadata() -> List[StrDict]:
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


def download_playlist_items(playlist_id) -> List[StrDict]:
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
    items1 = []
    for item in items:
        if len(item['snippet']['thumbnails']) == 0:
            # I've seen this for private videos
            continue
        video_id = item['contentDetails']['videoId']
        if video_id not in durations:
            # Private videos seem to appear in the playlistItems query, but you
            # don't get a duration with download_durations(). So just ignore them.
            continue
        item['duration'] = durations[video_id]
        items1.append(item)
    return items1


def download_durations(video_ids: List[str]) -> Dict[str, timedelta]:
    chunk_size = 50
    chunks = [video_ids[i:i + chunk_size] for i in range(0, len(video_ids), chunk_size)]
    durations: Dict[str, timedelta] = {}
    for chunk in chunks:
        r = execute(youtube.videos().list(part='contentDetails', id=','.join(chunk)))
        for video_id, item in zip(chunk, r['items']):
            # Sometimes duration is not available, I don't know why.
            duration0 = item['contentDetails'].get('duration')
            durations[video_id] = parse_duration(duration0) if duration0 else None
    return durations


def format_duration(td: timedelta) -> str:
    ts = int(td.total_seconds())
    tm, s = divmod(ts, 60)
    h, m = divmod(tm, 60)
    if h > 0:
        return f'{h}:{m:02}:{s:02}'
    else:
        return f'{m}:{s:02}'


def get_main_page(items: List[StrDict]):
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


def get_playlist_page(metadata: StrDict, items: List[StrDict]):
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


def get_list_page(title: str, items: List[ItemData]) -> str:
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


def download() -> Tuple[List[StrDict], List[List[StrDict]]]:
    playlists = download_playlists_metadata()
    playlist_items = []
    for playlist_id in PLAYLISTS:
        playlist_items.append(download_playlist_items(playlist_id))
    return playlists, playlist_items


def write_html(playlists: List[StrDict], playlist_items: List[List[StrDict]]) -> None:
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


def reimp() -> None:
    from inspect import currentframe

    cmd = "from importlib import reload; import allowed_videos; reload(allowed_videos); from allowed_videos import *"
    exec(cmd, currentframe().f_back.f_globals, currentframe().f_back.f_locals)


def main() -> None:
    playlists, playlist_items = download()
    write_html(playlists, playlist_items)


if __name__ == '__main__':
    main()
