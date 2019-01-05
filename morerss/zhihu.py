from urllib.parse import urljoin
import asyncio
import datetime
import json
import re
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

        baseurl = 'https://zhuanlan.zhihu.com/' + name
        url = 'https://zhuanlan.zhihu.com/api/columns/' + name
        info = await self._get_url(url)
        url = 'https://zhuanlan.zhihu.com/api/columns/%s/posts?limit=20' % name
        posts = await self._get_url(url)
        posts = await self._process_posts(posts)

        rss_info = {
            'title': '%s - 知乎专栏' % info.get('title', ''),
            'description': cdata(info.get('description', '')),
        }

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

    async def _process_posts(self, posts):
        data = []
        for item in posts['data']:
            res = await base.fetch_zhihu(item['url'])
            await asyncio.sleep(randint(1, 5))
            soup = BeautifulSoup(res.body.decode('utf-8'), features='lxml')
            item['content'] = soup.find(
                'div', class_='RichText ztext Post-RichText').text
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

    item = PyRSS2Gen.RSSItem(
        title=post['title'].replace('\x08', ''),
        link=url,
        guid=PyRSS2Gen.Guid(url),
        description=cdata(content),
        pubDate=datetime.datetime.fromtimestamp(post['created']),
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
