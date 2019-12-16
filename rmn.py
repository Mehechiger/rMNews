#!/usr/bin/python3
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
import newspaper
from newspaper import news_pool
import pdfkit
import os
from concurrent import futures
from collections import defaultdict
from datetime import datetime
import _pickle as pickle


rmapi_loc = "go run github.com/juruen/rmapi"  # rmapi location
sites = []  # list of sites
cwpath = os.getcwd()+"/"  # working path
pdf_options = {
    'page-height': '7.2in',
    'page-width': '5.4in',
    'encoding': 'UTF-8',
    'dpi': '300',
    'grayscale': '',
    'quiet': ''
}  # pdf gen options
stashed_artls = defaultdict(int)  # articles stashed to be downloaded later
pending_artls = set()  # pending articles
downloaded_artls = defaultdict(int)  # articles downloaded in the past
date = time = None  # date and time
retry = 50  # max time of download retry
n_config = newspaper.Config()
n_config.browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
n_config.fetch_images = False
"""
"""
n_config.memoize_articles = False
"""
"""


def path_check(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def acq_datetime():
    global date, time
    date, time = datetime.now().strftime('%m-%d\t%Hh%M').split("\t")


def rmapi(*cmds):
    return Popen("echo '%s' | %s" % ("\n".join(cmds), rmapi_loc), stdout=PIPE, shell=True).stdout.read()


def download_artls(artls):
    def saveas_pdf(title, url, path):
        path_check(path)
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

    dump_pending()
    dump_stashed()
    dump_downloaded()


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
        pending_artls.add((artl.title, artl.url, site_name))
    dump_pending()
    download_artls(pending_artls)


"""
combine all the load/dump funcs
"""


def load_pending():
    global pending_artls
    try:
        with open(cwpath+"pending_artls", "rb") as f:
            pending_artls = pickle.load(f)
    except FileNotFoundError:
        pass


def dump_pending():
    with open(cwpath+"pending_artls", "wb") as f:
        pickle.dump(pending_artls, f)


def load_stashed():
    global stashed_artls
    try:
        with open(cwpath+"stashed_artls", "rb") as f:
            stashed_artls = pickle.load(f)
    except FileNotFoundError:
        pass


def dump_stashed():
    with open(cwpath+"stashed_artls", "wb") as f:
        pickle.dump(stashed_artls, f)


def load_downloaded():
    global downloaded_artls
    try:
        with open(cwpath+"downloaded_artls", "rb") as f:
            downloaded_artls = pickle.load(f)
    except FileNotFoundError:
        pass


def dump_downloaded():
    with open(cwpath+"downloaded_artls", "wb") as f:
        pickle.dump(downloaded_artls, f)


if __name__ == "__main__":

    acq_datetime()

    """
    """
    """
    exit()
    """

    # read list of sites from file
    with open(cwpath+"sites.txt", "r") as f:
        sites = [line.split("\t") for line in f.read().split("\n")[:-1]]

    # load downloaded articles from file
    load_downloaded()

    # read pending articles from file
    # retry pending articles
    load_pending()
    download_artls(pending_artls)
    # read stashed articles from file
    # retry stashed articles
    load_stashed()
    download_artls(stashed_artls)

    for site in sites:
        acq_datetime()
        extr_src(*site)

        print(rmapi("ls", "cd psdt", "ls"))
