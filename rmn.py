#!/usr/bin/python3
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
import newspaper
from newspaper import news_pool
import pdfkit
import os
import shutil
import re
from collections import defaultdict
from datetime import datetime, timedelta
import _pickle as pickle


rmapi_loc = "~/go/bin/rmapi"  # rmapi location
sites = []  # list of sites
cwpath = os.getcwd()+"/"  # working path
pdf_options = {
    'page-height': '7.2in',
    'page-width': '5.4in',
    'margin-top': '0.2in',
    'margin-bottom': '0.2in',
    'margin-left': '0.15in',
    'margin-right': '0.15in',
    'encoding': 'UTF-8',
    'dpi': '300',
    'grayscale': '',
    'quiet': ''
}  # pdf gen options
stashed_artls = defaultdict(int)  # articles stashed to be downloaded later
pending_artls = set()  # pending articles
downloaded_artls = defaultdict(int)  # articles downloaded in the past
date = time = None  # date and time
stashed_retry = 50  # max time of stashed artl download retry
cleanup_thres = 100000  # max number of entries allowed before cleanup
n_config = newspaper.Config()
n_config.browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
n_config.fetch_images = False
"""
"""
n_config.memoize_articles = False
"""
"""


def check_mkdir(path, retry=10):
    for i in range(retry):
        if os.path.isdir(path):
            return
        else:
            os.makedirs(path)


def exists_artl(path, title):
    return title[6:] in (d[6:-4] for d in os.listdir(path))


def acq_datetime():
    global date, time
    date, time = datetime.now().strftime('%m-%d\t%Hh%M').split("\t")


def chdir(path, retry=10):
    for i in range(retry):
        os.chdir(path)
        if os.getcwd()+"/" == path:
            return
    print("fatal error: can't chdir")
    exit()


def rmtree(path, retry=10):
    for i in range(retry):
        if not os.path.isdir(path):
            return
        else:
            shutil.rmtree(path)
    print("fatal error: can't rmtree")
    exit()


def rmapi(*cmds):
    return Popen("echo '%s' | %s" % ("\n".join(cmds), rmapi_loc), stdout=PIPE, shell=True).stdout.read().decode(encoding="utf_8")


def r_mput(retry=10):
    print("uploading news to cloud...")
    path = cwpath+"downloaded/"
    if not os.path.isdir(path):
        return

    chdir(path)

    mput_errors = "failed to create directory|failed to upload file"
    for i in range(retry):
        if re.compile(mput_errors).search(rmapi("mkdir News", "mput /News")) == None:
            break

    rmtree(path)
    chdir(cwpath)


def r_rmtree(*r_paths):
    def r_tree(r_path):
        ls_list = rmapi("ls \"%s\"" % r_path)
        ds = re.compile("(?<=\[d\]\t).*(?=\n)").findall(ls_list)
        fs = re.compile("(?<=\[f\]\t).*(?=\n)").findall(ls_list)
        br = " ".join("\"%s/%s\"" % (r_path, f) for f in fs)
        if ds:
            for d in ds:
                return "%s %s \"%s/%s\"" % (br, r_tree("%s/%s" % (r_path, d)), r_path, d)
        else:
            return br

    r_trees = ""
    for r_path in r_paths:
        r_trees = "%s %s \"%s\"" % (r_trees, "".join(r_tree(r_path)), r_path)
    rmapi("rm %s" % r_trees)


def r_del_old(n_days=7):
    date_old = datetime.strptime(date, "%m-%d")-timedelta(days=n_days)

    news_dirs = re.compile(
        "(?<=\[d\]\t)\d\d-\d\d.*(?=\n)").findall(rmapi("ls News"))

    news_days = [news_dir[:5] for news_dir in news_dirs]

    to_del = ["News/%s" % news_dirs[i]
              for i in range(len(news_dirs)) if datetime.strptime(news_days[i], "%m-%d") < date_old]

    if to_del:
        r_rmtree(*to_del)


def download_artls(artls):
    def saveas_pdf(title, url, path):
        check_mkdir(path)
        if exists_artl(path, title):
            return True
        try:
            pdfkit.from_url(url, path+title+".pdf", pdf_options)
            return True
        except OSError:
            if os.path.exists(path+title+".pdf"):
                return True
            else:
                return False

    def download_artl(title, url, site_name):
        global stashed_artls, pending_artls, downloaded_artls
        if stashed_artls[(title, url, site_name)] > stashed_retry:
            return
        if saveas_pdf("%s %s" % (time, title), url, "%s/downloaded/%s %s/" % (cwpath, date, site_name)):
            downloaded_artls[url] = 1
            try:
                pending_artls.remove((title, url, site_name))
            except KeyError:
                pass
            try:
                stashed_artls.pop((title, url, site_name))
            except KeyError:
                pass
            print("%s %s downloaded" % (time, title))
        else:
            stashed_artls[(title, url, site_name)] += 1
            print("%s stashed" % title)

    for title, url, site_name in artls.copy():
        if downloaded_artls[url]:
            continue
        download_artl(title, url, site_name)

    dump("pending_artls", "stashed_artls", "downloaded_artls")
    r_mput()


def extr_src(lan, site_name, site_url):
    global pending_artls, n_config
    n_config.language = lan
    src = newspaper.build(site_url, config=n_config)
    news_pool.set([src, ], threads_per_source=5)
    news_pool.join()
    for artl in src.articles:
        try:
            artl.parse()
        except:
            try:
                artl.parse()
            except:
                print("error, passed")
                continue
        pending_artls.add((artl.title.replace("/", ""), artl.url, site_name))
        """
        """
        print("kkkkkkk", artl.title.replace("/", ""))
        """
        """
    dump("pending_artls")
    download_artls(pending_artls)


def load(*somethings):
    for something in somethings:
        try:
            with open(cwpath+something, "rb") as f:
                globals()[something] = pickle.load(f)
        except FileNotFoundError:
            pass


def dump(*somethings):
    for something in somethings:
        with open(cwpath+something, "wb") as f:
            pickle.dump(globals()[something], f)


def cleanup(*somethings):
    for something in somethings:
        if len(globals()[something]) > cleanup_thres:
            n = int(len(globals()[something])*0.1)
            for key in globals()[something].copy():
                if n > 0:
                    try:
                        globals()[something].pop(key)
                    except TypeError:
                        globals()[something].remove(key)
                n -= 1
    dump(*somethings)


if __name__ == "__main__":
    while 1:
        acq_datetime()
        print("\n", "fresh new round at %s %s" % (date, time))

        # del old news
        print("deleting old news...")
        r_del_old()

        # read list of sites from file
        print("loading sites to parse...")
        with open(cwpath+"sites.txt", "r") as f:
            sites = [line.split("\t") for line in f.read().split("\n")[:-1]]

        # load downloaded articles from file
        print("loading list of downloaded articles...")
        load("downloaded_artls")

        # read pending articles from file
        # retry pending articles
        print("loading list of unfinished pending articles...", end=" ")
        load("pending_artls")
        print("retrying...")
        download_artls(pending_artls)

        # read stashed articles from file
        # retry stashed articles
        print("loading list of stashed articles...", end=" ")
        load("stashed_artls")
        print("retrying...")
        download_artls(stashed_artls)

        for site in sites:
            print("processing site %s..." % site[1])
            acq_datetime()
            extr_src(*site)

        print("cleaning up...")
        cleanup("downloaded_artls", "stashed_artls", "pending_artls")
