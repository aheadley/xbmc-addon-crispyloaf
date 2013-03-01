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

from xbmcswift2 import Plugin

from resources.lib.crispyloaf_lib import CrispyLoafHelper
from crunchyroll.constants import META

plugin = Plugin()

helper = CrispyLoafHelper(plugin)

@plugin.route('/', name='index')
@plugin.route('/categories/')
def show_categories():
    return helper.get_category_list()

@plugin.route('/category/<category>/')
def show_category_series(category):
    return helper.get_series_list(category)

@plugin.route('/series/<series_id>/')
def show_series(series_id):
    return helper.get_episode_list(series_id)

@plugin.route('/episode/<media_id>/')
def play_episode(media_id):
    return helper.play_episode(media_id)

@plugin.route('/queue/anime/', name='anime_queue', options={'media_types': META.TYPE_ANIME})
@plugin.route('/queue/drama/', name='drama_queue', options={'media_types': META.TYPE_DRAMA})
@plugin.route('/queue/')
def show_queue(media_types='|'.join([META.TYPE_ANIME, META.TYPE_DRAMA])):
    return helper.get_queue(media_types)

if __name__ == '__main__':
    plugin.run()
