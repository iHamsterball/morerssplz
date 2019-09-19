#!/usr/bin/python
# -*- coding: utf-8 -*-
from urllib.parse import urljoin
import asyncio
import datetime
import json
import re
import html
import html.parser
import itertools
from functools import partial
from random import randint

import PyRSS2Gen
from lxml.html import fromstring, tostring
from bs4 import BeautifulSoup

from .base import BaseHandler
from . import base

re_br_to_remove = re.compile(r'(?:<br>)+')
re_img = re.compile(r'<img [^>]*?src="([^h])')
re_zhihu_img = re.compile(r'https://\w+\.zhimg\.com/.+')

picN = iter(itertools.cycle('1234'))


def abs_img(m):
    return '<img src="https://pic%s.zhimg.com/' % next(picN) + m.group(1)


class ZhihuZhuanlanHandler(BaseHandler):
    async def get(self, name):
        self.key = 'rss:zhihuzhuanlan:{}'.format(name)
        loop = asyncio.get_event_loop()
        loop.create_task(self._update(name))
        if self.redis.exists(self.key):
            parser = html.parser.HTMLParser()
            xml = self.redis.get(self.key)
            xml = parser.unescape(xml)
        else:
            rss = PyRSS2Gen.RSS2(
                title='',
                link='',
                lastBuildDate=datetime.datetime.now(),
                generator='morerssplz %s' % (base.__version__),
                description='',
            )
            xml = rss.to_xml(encoding='utf-8')
        self.finish(xml)

    async def _update(self, name):
        pic = self.get_argument('pic', None)
        digest = self.get_argument('digest', False) == 'true'

        info = await self._get_info(name)
        rss_info = {
            'title': '%s - 知乎专栏' % info.get('title', ''),
            'description': cdata(info.get('description', '')),
        }

        baseurl = 'https://zhuanlan.zhihu.com/' + name
        url = 'https://zhuanlan.zhihu.com/api/columns/%s/articles' % name

        authors = set()
        coroutines = list()
        articles = await self._get_articles(url, offset=0, limit=100)
        for article in articles:
            author = article.get('author').get('url_token')
            if author not in authors:
                authors.add(author)
                coroutines.append(await self._get_library(author))
        library = await asyncio.gather(*coroutines)
        library = dict((article.get('id'), article) for article in library[0])
        posts = list(library.get(article.get('id')) for article in articles)

        rss = base.data2rss(
            baseurl,
            rss_info, posts,
            partial(post2rss, url, digest=digest, pic=pic),
        )
        xml = rss.to_xml(encoding='utf-8')
        self.redis.set(self.key, xml)

    async def _get_url(self, url):
        res = await base.fetch_zhihu(url)
        info = json.loads(res.body.decode('utf-8'))
        return info

    async def _get_info(self, name):
        url = 'https://zhuanlan.zhihu.com/api/columns/' + name
        return await self._get_url(url)

    async def _get_articles(self, url, offset, limit):
        res = await base.fetch_zhihu('{}{}{}{}'.format(
            url,
            '&' if '?' in url else '?',
            'offset={}'.format(offset),
            '&limit={}'.format(limit)))
        res = json.loads(res.body.decode('utf-8'))
        data = res.get('data')
        paging = res.get('paging')
        if not paging.get('is_end') and offset == 0:
            totals = paging.get('totals')
            coroutines = list()
            while offset < totals:
                offset += limit
                coroutines.append(self._get_articles(url, offset, limit))
            rest = await asyncio.gather(*coroutines)
            for result in rest:
                data.extend(result)
        return data

    async def _get_library(self, author):
        parameters = '?sort_by=created&include=data%5B*%5D.content'
        url = 'https://www.zhihu.com/api/v4/members/{}/articles{}'.format(
            author, parameters)
        return self._get_articles(url, offset=0, limit=20)

    async def _process_posts(self, posts):
        data = []
        for item in posts['data']:
            res = await base.fetch_zhihu(item['url'])
            await asyncio.sleep(randint(1, 5))
            soup = BeautifulSoup(res.body.decode('utf-8'), features='lxml')
            item['content'] = str(
                soup.find('div', class_='RichText ztext Post-RichText'))
            data.append(item)
        return data


def parse_time(t):
    t = ''.join(t.rsplit(':', 1))
    return datetime.datetime.strptime(t, '%Y-%m-%dT%H:%M:%S%z')


def process_content(text):
    text = re_br_to_remove.sub(r'', text)
    text = re_img.sub(abs_img, text)
    text = text.replace('<img ', '<img referrerpolicy="no-referrer" ')
    text = text.replace('<code ', '<pre><code ')
    text = text.replace('</code>', '</code></pre>')
    text = text.replace('<div>', '')
    text = text.replace('</div>', '')
    text = text.replace('<div class="RichText ztext Post-RichText">', '')
    return text


def cdata(text):
    return '<![CDATA[{}]]>'.format(text)


def post2rss(baseurl, post, *, digest=False, pic=None):
    url = urljoin(baseurl, post['url'])
    if digest:
        content = post['excerpt'].strip()
    elif post.get('title_image'):
        content = '<p><img src="%s"></p>' % post['title_image'] + \
            post['content']
    else:
        content = post['content']

    if content:
        content = process_content(content)

        doc = fromstring(content)
        if pic:
            base.proxify_pic(doc, re_zhihu_img, pic)
        content = tostring(doc, encoding=str)
        content = content.replace('<div>', '')
        content = content.replace('</div>', '')

    item = PyRSS2Gen.RSSItem(
        title=post['title'].replace('\x08', ''),
        link=url,
        guid=PyRSS2Gen.Guid(url),
        description=content,
        pubDate=datetime.datetime.utcfromtimestamp(post['updated']),
        author=post['author']['name'],
    )
    return item


def test(url):
    import requests
    column = url.rsplit('/', 1)[-1]
    baseurl = url

    s = requests.Session()
    s.headers['User-Agent'] = 'curl/7.50.1'
    # s.verify = False
    url = 'https://zhuanlan.zhihu.com/api/columns/' + column
    info = s.get(url).json()
    url = 'https://zhuanlan.zhihu.com/api/columns/%s/posts' % column
    posts = s.get(url).json()

    rss_info = {
        'title': '%s - 知乎专栏' % info.get('title', ''),
        'description': info.get('description', ''),
    }
    rss = base.data2rss(
        baseurl,
        rss_info, posts,
        partial(post2rss, url, pic='cf'),
    )
    return rss


if __name__ == '__main__':
    import sys
    test(sys.argv[1]).write_xml(sys.stdout, 'utf-8')
