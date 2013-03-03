# -*- coding: utf-8 -*-

# Copyright (C) 2013  Alex Headley  <aheadley@waysaboutstuff.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import time
import os.path
import logging
import sys

from xbmcswift2 import xbmc
from xbmcswift2.logger import setup_log

setup_log('crunchyroll')

from crunchyroll.constants import META
from crunchyroll.models import DictModel
from crunchyroll.apis.meta import MetaApi
from crunchyroll.util import xml_node_to_string

logger = setup_log(__name__)

def save_state(func):
    def inner_func(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self._storage['api_state'] = self._api.get_state()
        return result
    return inner_func

def wait_for_playing(limit=30):
    player = xbmc.Player()
    for _ in xrange(limit):
        if player.isPlaying():
            return player
        time.sleep(1)
    else:
        raise Exception('No video started playing within %d seconds' % limit)

class CrispyLoafHelper(object):
    def __init__(self, plugin_obj):
        self._plugin = plugin_obj
        self._storage = self._plugin.get_storage(file_format='json')
        self._init()

    def get_category_list(self):
        categories = [
            {
                'label': 'Anime',
                'path': self._plugin.url_for('show_category_series', category='anime'),
            },
            {
                'label': 'Drama',
                'path': self._plugin.url_for('show_category_series', category='drama'),
            },
            {
                'label': 'Queue',
                'path': self._plugin.url_for('show_queue'),
            },
        ]
        return categories

    @save_state
    def get_series_list(self, category):
        series = getattr(self._api, 'list_%s_series' % category)(sort=META.SORT_ALPHA)
        return map(self._make_series_item, series)

    @save_state
    def get_episode_list(self, series_id):
        episodes = self._api.list_media(self._make_mock_series(series_id),
            sort=META.SORT_ASC)
        return map(self._make_episode_item, (e \
            for e in episodes \
                if self._filter_episode(e)))

    @save_state
    def play_episode(self, media_id):
        media_item = self._make_mock_media(media_id)
        video_quality_setting = self._plugin.get_setting('stream_quality')
        logger.info('Trying to find stream params for video quality: %s',
            video_quality_setting)
        video_formats = self._api.get_stream_formats(media_item)
        try:
            video_format, video_quality = video_formats[video_quality_setting]
        except KeyError as err:
            logger.error('Got error loading stream format/quality: %s',
                err)
            logger.info('Using default format and quality')
            video_format = 106
            video_quality = 60
        logger.info('Using video format/quality: %d/%d', video_format, video_quality)
        stream = self._api.get_media_stream(media_item,
            format=video_format, quality=video_quality)
        logger.debug('Got stream object: %r', stream)
        if stream.stream_info.is_upsell:
            logger.error('Got upsell tag, redirecting')
            self._plugin.notify('Content is only available to premium members')
            return self._plugin.redirect(self._plugin.url_for('index'))
        rtmp_data = stream.stream_info.rtmp_data
        logger.debug('Got RTMP data: %r', rtmp_data)
        if rtmp_data is None:
            logger.error('RTMP data was none, redirecting to index')
            self._plugin.notify('Failed to load RTMP stream data')
            return self._plugin.redirect(self._plugin.url_for('index'))
        item = {
            'label': stream.findfirst(
                './/{default}preload/media_metadata/episode_title').text,
            'path': self._make_rtmp_url(rtmp_data),
            'is_playable': True,
        }
        sub_file = self._get_subtitle_file(stream, media_id)
        logger.info('Playing #%s ("%s") at f:%d/q:%d with sub file: %r',
            media_id, item['label'], video_format, video_quality, sub_file)
        result = self._plugin.play_video(item)
        if sub_file is not None:
            self._add_subtitles(sub_file)
        return result

    def get_queue(self, media_types):
        return map(self._make_series_item, self._api.list_queue(media_types))

    def _filter_episode(self, episode):
        if self._plugin.get_setting('hide_clips') == 'true':
            if not episode.episode_number:
                return False
        if not episode.premium_available:
            return False
        if not self._api.is_premium(episode.media_type) and not episode.free_available:
            return False
        return True

    def _init(self):
        logger = self._plugin.log
        logger.info('Initializing helper')
        username = self._plugin.get_setting('username')
        password = self._plugin.get_setting('password')
        if username and password:
            logger.debug('Found username and password, using for api init')
            self._api = MetaApi(username=username, password=password)
        else:
            logger.debug('No username and/or password found, init api without')
            self._api = MetaApi()
        state = self._storage.get('api_state')
        if state:
            logger.info('Found previous state, loading into api: %r', state)
            # self._api.set_state(state)

    def _add_subtitles(self, sub_file_name):
        return wait_for_playing().setSubtitles(sub_file_name)

    def _get_subtitle_file(self, stream, media_id):
        try:
            sub_id = stream.default_subtitles.id
        except ValueError:
            logger.info('No subtitle tag found for media ID #%s, assuming hard-subs',
                media_id)
            return None
        sub_file = self._plugin.temp_fn('cr_%s_%s.ass' % (media_id, stream.default_subtitles.id))
        if not os.path.exists(sub_file):
            try:
                handle = open(sub_file, 'w')
                handle.write(stream.default_subtitles.decrypt().get_ass_formatted())
            finally:
                handle.close()
        return sub_file

    def _make_series_item(self, series):
        item = {
            'label': series.name,
            'path': self._plugin.url_for('show_series', series_id=series.series_id)
        }
        return item

    def _make_episode_item(self, episode):
        item = {
            'label': u'E%02d - %s' % (int(episode.episode_number), episode.name),
            'path': self._plugin.url_for('play_episode', media_id=episode.media_id),
            'is_playable': False,
        }
        return item

    def _make_rtmp_url(self, rtmp_data):
        fmt_string = '{url} swfurl={swf_url} swfvfy=1 token={token} playpath={file} ' \
            'pageurl={page_url} tcUrl={url}'
        return fmt_string.format(**rtmp_data)

    def _make_mock_media(self, media_id):
        return DictModel({'media_id': media_id})

    def _make_mock_series(self, series_id):
        return DictModel({'series_id': series_id})
