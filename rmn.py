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
import pickle
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import threading


rmapi_loc = "~/go/bin/rmapi"  # rmapi location
cwpath = os.getcwd()+"/"  # working path

pdf_options = {
    'page-height': '6.4in',
    'page-width': '4.8in',
    'margin-top': '0.2in',
    'margin-bottom': '0.2in',
    'margin-left': '0.15in',
    'margin-right': '0.15in',
    'encoding': 'UTF-8',
    'dpi': '300',
    'grayscale': '',
    'quiet': ''
}  # pdf gen options
n_config = newspaper.Config()
n_config.browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
n_config.fetch_images = False
"""
n_config.memoize_articles = False
"""
"""
"""

sites = []  # list of sites
stashed_artls = defaultdict(int)  # articles stashed to be downloaded later
pending_artls = set()  # pending articles
downloaded_artls = defaultdict(int)  # articles downloaded in the past

date = time = None  # date and time
last_rdelold = None  # last r_del_old() date

stashed_retry = 50  # max time of stashed artl download retry
cleanup_thres = 100000  # max number of entries allowed before cleanup
t_per_site = 10  # max number of threads per site
t_sites = 10  # max number of threads to build sites

lock = threading.Lock()


def check_mkdir(path, retry=10):
    for i in range(retry):
        if os.path.isdir(path):
            return
        else:
            os.makedirs(path)
    print("fatal error: can't mkdir")
    exit()


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
    print("uploading news to cloud...", end="\r")
    path = cwpath+"downloaded/"
    if not os.path.isdir(path):
        print("uploading news to cloud... nothing to upload")
        return

    chdir(path)

    mput_errors = "failed to create directory|failed to upload file"
    for i in range(retry):
        if re.compile(mput_errors).search(rmapi("mkdir News", "mput /News")) == None:
            break

    rmtree(path)
    chdir(cwpath)
    print("uploading news to cloud... done")


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
    global last_rdelold
    last_rdelold = last_rdelold if last_rdelold else datetime.now()-timedelta(hours=6)
    if datetime.now() > last_rdelold+timedelta(hours=6):
        last_rdelold = datetime.now()
        print("deleting old news...", end="\r")
        date_old = datetime.strptime(date, "%m-%d")-timedelta(days=n_days)

        news_dirs = re.compile(
            "(?<=\[d\]\t)\d\d-\d\d.*(?=\n)").findall(rmapi("ls News"))

        news_days = [news_dir[:5] for news_dir in news_dirs]

        to_del = ["News/%s" % news_dirs[i]
                  for i in range(len(news_dirs)) if datetime.strptime(news_days[i], "%m-%d") < date_old]

        if to_del:
            r_rmtree(*to_del)
            print("deleting old news... done")
        else:
            print("deleting old news... nothing to delete")


def download_artls_mt(artls):
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

    def download_artl_st(title, url, site_name):
        global stashed_artls, pending_artls, downloaded_artls

        lock.acquire()
        if stashed_artls[(title, url, site_name)] < stashed_retry:
            if downloaded_artls[title] or downloaded_artls[url]:
                try:
                    pending_artls.remove((title, url, site_name))
                except KeyError:
                    pass
                try:
                    stashed_artls.pop((title, url, site_name))
                except KeyError:
                    pass
                lock.release()

                print("downloading %s %s... already downloaded" % (time, title))
            else:
                lock.release()

                if saveas_pdf("%s %s" % (time, title), url, "%s/downloaded/%s %s/" % (cwpath, date, site_name)):

                    lock.acquire()
                    try:
                        pending_artls.remove((title, url, site_name))
                    except KeyError:
                        pass
                    try:
                        stashed_artls.pop((title, url, site_name))
                    except KeyError:
                        pass
                    downloaded_artls[url] = 1
                    downloaded_artls[title] = 1
                    lock.release()

                    print("downloading %s %s... done" % (time, title))
                else:

                    lock.acquire()
                    stashed_artls[(title, url, site_name)] += 1
                    lock.release()

                    print("downloading %s %s... stashed" % (time, title))
        else:
            lock.release()

    acq_datetime()
    with ThreadPoolExecutor(max_workers=t_per_site) as executor:
        for title, url, site_name in artls.copy():
            executor.submit(download_artl_st, title, url, site_name)

    dump("pending_artls", "stashed_artls", "downloaded_artls")


def extr_src_mt(sites):
    def extr_src_st(lan, site_name, site_url, kwarg=None, val=None):
        global pending_artls, n_config
        n_config.language = lan
        src = newspaper.build(site_url, config=n_config)
        if src.size():
            news_pool.set([src, ], threads_per_source=t_per_site)
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
                try:
                    if kwarg:
                        artl_title = BeautifulSoup(artl.html, "html.parser").find(
                            attrs={kwarg: val}).string
                    else:
                        artl_title = artl.title

                    lock.acquire()
                    pending_artls.add(
                        (artl_title.replace("/", ""), artl.url, site_name))
                    lock.release()

                except:
                    pass

            lock.acquire()
            dump("pending_artls")
            lock.release()

            print("downloading %d articles from %s" % (src.size(), site_name))
            download_artls_mt(pending_artls)

        else:
            print("nothing to download from %s" % site_name)

    with ThreadPoolExecutor(max_workers=t_sites) as executor:
        print("processing %d sites..." % len(sites))
        for site in sites:
            executor.submit(extr_src_st, *site)


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
    print("cleaning up...")
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
        r_del_old()

        # load downloaded articles from file
        print("loading list of downloaded articles...")
        load("downloaded_artls")

        # read pending articles from file
        # retry pending articles
        print("loading list of unfinished pending articles...", end="\r")
        load("pending_artls")
        if pending_artls:
            print("loading list of unfinished pending articles... retrying...")
            download_artls_mt(pending_artls)
        else:
            print("loading list of unfinished pending articles... nothing to retry")

        # read stashed articles from file
        # retry stashed articles
        print("loading list of stashed articles...", end="\r")
        load("stashed_artls")
        if stashed_artls:
            print("loading list of stashed articles... retrying...")
            download_artls_mt(stashed_artls)
        else:
            print("loading list of stashed articles... nothing to retry")

        # read list of sites from file
        print("loading sites to parse...")
        with open(cwpath+"sites.txt", "r") as f:
            sites = [line.split("\t") for line in f.read().split("\n")[:-1]]
        extr_src_mt(sites)

        r_mput()

        cleanup("downloaded_artls", "stashed_artls", "pending_artls")
