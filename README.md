# morerssplz

![GitHub](https://img.shields.io/github/license/iHamsterball/morerssplz)
![Requires.io](https://img.shields.io/requires/github/iHamsterball/morerssplz)
![Uptime Robot status](https://img.shields.io/uptimerobot/status/m781831254-e4a851d57016681cbdc4855a)
![Uptime Robot ratio (7 days)](https://img.shields.io/uptimerobot/ratio/7/m781831254-e4a851d57016681cbdc4855a)
![GitHub top language](https://img.shields.io/github/languages/top/iHamsterball/morerssplz)

一个将未提供源订阅的网站转为 RSS 源的服务，网站的使用方法见 [https://rss.lilydjwg.me/](https://rss.lilydjwg.me/)。

## 支持列表

- 知乎专栏
- 知乎动态
- V2EX 评论

## 依赖

- Python >= 3.5
- Tornado >= 5 (旧版本可能也可以用）
- PyRSS2Gen
- BeautifulSoup
- lxml
- pycurl
- redis

> 代理支持模块 `morerss.proxy` 是故意不提交的。如果需要，请自行实现。

## 许可

此项目及其上游项目均使用 GPLv3 许可证，请遵守协议要求使用。

## 注意

此项目与其上游项目已经分叉，上游项目的部分更新可能不会被合并进此项目，此项目在某些实现上也会与上游项目不同。
