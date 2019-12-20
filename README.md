# rMNews

**Dependencies**

juruen/rmapi

wkhtmltopdf

Python3: newspaper3k, pdfkit, bs4



**Installation**

Copy rmn.py and sites.txt to somewhere you want, but keep them in the same folder. Then modify the sites.txt to get your favorite news, here's an example:

| 1    | 2        | 3                       | 4     | 5                 |
| ---- | -------- | ----------------------- | ----- | ----------------- |
| zh   | 知乎日报 | https://daily.zhihu.com | class | DailyHeader-title |
| zh   | cnBeta   | https://cnbeta.com      |       |                   |
| zh   | 果壳     | https://guokr.com       |       |                   |

Each line is an entry for a specific site and infos are seperated by tabulations, in the order:

1. language (see https://newspaper.readthedocs.io/en/latest/user_guide/quickstart.html bottom of page)
2. site name
3. site url
4. keyword argument for BeautifulSoup
5. content of the keyword argument

4 and 5 are optional and for some special sites, the real title of whose articles are not embedded in the "title" tag but somewhere else. In case you need them, check https://www.crummy.com/software/BeautifulSoup/bs4/doc/ (you might need to look into the source code of the site as well)



**And...?**

Just run it with python3 rmn.py or perhaps as some suggested, set it up as a system daemon.