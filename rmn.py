#!/usr/bin/python3
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
import newspaper
from newspaper import news_pool
import pdfkit
import os
from collections import defaultdict
from datetime import datetime
import _pickle as pickle


rmapi_loc = "go run github.com/juruen/rmapi"  # rmapi location
sites = []  # list of sites
rpath = "./"  # working path
pdf_options = {
    'page-height': '7.2in',
    'page-width': '5.4in',
    'encoding': 'UTF-8',
    'dpi': '400',
    'quiet': ''
}  # pdf gen options
stashed_artls = defaultdict(int)  # articles stashed to be downloaded later
pending_artls = set()  # pending articles
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


def load_pending():
    global pending_artls
    try:
        with open(rpath+"pending_artls", "rb") as f:
            pending_artls = pickle.load(f)
    except FileNotFoundError:
        pass


def dump_pending():
    with open(rpath+"pending_artls", "wb") as f:
        pickle.dump(pending_artls, f)


def download_artl(title, url, site_name):
    global stashed_artls, pending_artls
    if saveas_pdf(title, url, "%s/downloaded/%s %s/" % (rpath, date, site_name)):
        try:
            pending_artls.remove((title, url, site_name))
            stashed_artls.pop((title, url, site_name))
        except KeyError:
            pass
        print("%s downloaded" % title)
    else:
        stashed_artls[(title, url, site_name)] += 1
        print("%s stashed" % title)


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
        pending_artls.add(("%s %s" % (time, artl.title), artl.url, site_name))
    dump_pending()
    for title, url, site_name in pending_artls.copy():
        download_artl(title, url, site_name)
    dump_pending()


def load_stashed():
    global stashed_artls
    try:
        with open(rpath+"stashed_artls", "rb") as f:
            stashed_artls = pickle.load(f)
    except FileNotFoundError:
        pass


def dump_stashed():
    with open(rpath+"stashed_artls", "wb") as f:
        pickle.dump(stashed_artls, f)


if __name__ == "__main__":

    acq_datetime()

    """
    exit()
    """
    """
    """

    # read list of sites from file
    with open(rpath+"sites.txt", "r") as f:
        sites = [line.split("\t") for line in f.read().split("\n")[:-1]]

    # read pending articles from file
    # retry pending articles
    load_pending()
    for title, url, site_name in pending_artls.copy():
        download_artl(title, url, site_name)
    dump_pending()
    # read stashed articles from file
    # retry stashed articles
    load_stashed()
    for title, url, site_name in stashed_artls.copy():
        download_artl(title, url, site_name)
    dump_stashed()

    for site in sites:
        acq_datetime()
        extr_src(*site)

        # write stashed articles to file
        dump_stashed()

        print(rmapi("ls", "cd psdt", "ls"))
