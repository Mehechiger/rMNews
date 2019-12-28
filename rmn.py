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
# articles stashed to be downloaded later
stashed_artls = defaultdict(lambda: (int(), datetime.now()))
stashed_artls['sites'] = set()  # sites stashed
pending_artls = set()  # pending articles
downloaded_artls = defaultdict(int)  # articles downloaded in the past

date = time = None  # date and time
last_rdelold = None  # last r_del_old() date

stashed_retry = 50  # max time of stashed artl download retry
cleanup_thres = 100000  # max number of entries allowed before cleanup
t_per_site = 5  # max number of threads per site
t_sites = 3  # max number of threads to build sites

stashed_lock = threading.Lock()
pending_lock = threading.Lock()
downloaded_lock = threading.Lock()
stashed_file_lock = threading.Lock()
pending_file_lock = threading.Lock()
downloaded_file_lock = threading.Lock()


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
        if not re.compile(mput_errors).search(rmapi("mkdir News", "mput /News")):
            break

    rmtree(path)
    chdir(cwpath)
    print("uploading news to cloud... done")


def r_rmtree(*r_paths):
    def r_tree(r_path, cond=lambda x: 1):
        ls_list = rmapi("ls \"%s\"" % r_path) if cond(r_path) else ""
        ds = re.compile("(?<=\[d\]\t).*(?=\n)").findall(ls_list)
        fs = re.compile("(?<=\[f\]\t).*(?=\n)").findall(ls_list)
        br = " ".join("\"%s/%s\"" % (r_path, f)
                      for f in fs if cond(r_path) and cond(f))
        if ds:
            for d in ds:
                return "%s %s \"%s/%s\"" % (br, r_tree("%s/%s" % (r_path, d), cond=cond), r_path, d) if cond(r_path) and cond(d) else br
        else:
            return br

    r_trees = ""
    for r_path in r_paths:
        r_trees = "%s %s \"%s\"" % (r_trees, "".join(r_tree(r_path)), r_path)
    if re.compile("Uknown rune").search(rmapi("rm %s" % r_trees)):
        print("Error deleting articles from cloud: Uknown rune. retrying with restricted mode...")
        r_trees = ""
        for r_path in r_paths:
            r_trees = "%s %s" % (r_trees, "".join(
                r_tree(r_path, cond=lambda x: re.search("\"", x) == None)))
        print(rmapi("rm %s" % r_trees))


def r_del_old(n_days=3):
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


def download_artls_mt(*artls):
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

        stashed_lock.acquire()
        stashed_retried, stashed_time = stashed_artls[(title, url, site_name)]
        stashed_lock.release()

        if stashed_retried < stashed_retry:
            print("k", title)
            if stashed_retried > stashed_retry/5:

                stashed_lock.acquire()
                if not site_name in stashed_artls['sites']:
                    stashed_artls['sites'].add(site_name)
                    print("site %s now in the cooling list" % site_name)
                stashed_lock.release()

            elif stashed_time+timedelta(hours=stashed_retried) < datetime.now():

                downloaded_lock.acquire()
                if downloaded_artls[url]:
                    downloaded_lock.release()

                    stashed_lock.acquire()
                    try:
                        stashed_artls.pop((title, url, site_name))
                    except KeyError:
                        pass
                    stashed_lock.release()

                    print("downloading %s %s... already downloaded" %
                          (time, title))
                else:
                    downloaded_lock.release()

                    if saveas_pdf("%s %s" % (time, title), url, "%s/downloaded/%s %s/" % (cwpath, date, site_name)):

                        stashed_lock.acquire()
                        try:
                            stashed_artls.pop((title, url, site_name))
                        except KeyError:
                            pass
                        try:
                            stashed_artls['site'].remove(site_name)
                            print("site %s now defrosted" % site_name)
                        except KeyError:
                            pass
                        stashed_lock.release()

                        downloaded_lock.acquire()
                        downloaded_artls[url] = 1
                        downloaded_lock.release()

                        print("downloading %s %s... done" % (time, title))
                    else:

                        stashed_lock.acquire()
                        stashed_artls[(title, url, site_name)
                                      ][1] = datetime.now()
                        stashed_artls[(title, url, site_name)][0] += 1
                        stashed_lock.release()

                        print("downloading %s %s... stashed" % (time, title))
            else:
                print("%s %s freshly stashed, cooling down for %s before retry..." % (
                    time, title, stashed_time+timedelta(hours=stashed_retried)-datetime.now()))
        elif stashed_retried == stashed_retry:

            stashed_lock.acquire()
            stashed_artls[(title, url, site_name)][1] = datetime.now()
            stashed_artls[(title, url, site_name)][0] += 1
            stashed_lock.release()

            print("%s %s permanently stashed" % (time, title))
        else:
            pass

        pending_lock.acquire()
        try:
            pending_artls.remove((title, url, site_name))
        except KeyError:
            pass
        pending_lock.release()

    artls = [artl for it in artls for artl in it]
    if artls:
        acq_datetime()
        with ThreadPoolExecutor(max_workers=t_per_site) as executor:
            for title, url, site_name in artls:
                executor.submit(download_artl_st, title, url, site_name)
        dump_mt("pending_artls", "stashed_artls", "downloaded_artls")


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

                    pending_lock.acquire()
                    pending_artls.add(
                        (re.compile("[/\"\']").sub("", artl_title), artl.url, site_name))
                    pending_lock.release()

                except:
                    pass

            dump_mt("pending_artls")

            print("downloading %d articles from %s" % (src.size(), site_name))
            download_artls_mt(pending_artls)

        else:
            print("nothing to download from %s" % site_name)

    with ThreadPoolExecutor(max_workers=t_sites) as executor:
        print("processing %d sites..." % len(sites))
        for site in sites:
            stashed_lock.acquire()
            if site[1] in stashed_artls['sites']:
                stashed_lock.release()
                print("site %s is in the cooling list, skipped..." % site[1])
            else:
                stashed_lock.release()
                executor.submit(extr_src_st, *site)


def load_mt(*somethings):
    def load_st(something):
        with globals()["%s_lock" % something[:-6]]:
            try:
                with open(cwpath+something, "rb") as f:
                    globals()[something] = pickle.load(f)
            except FileNotFoundError:
                pass

    with ThreadPoolExecutor(max_workers=3) as executor:
        for something in somethings:
            executor.submit(load_st, something)


def dump_mt(*somethings):
    def dump_st(something):
        with globals()["%s_lock" % something[:-6]]:
            with globals()["%s_file_lock" % something[:-6]]:
                with open(cwpath+something, "wb") as f:
                    pickle.dump(globals()[something], f)

    with ThreadPoolExecutor(max_workers=3) as executor:
        for something in somethings:
            executor.submit(dump_st, something)


def cleanup_mt(*somethings):
    def cleanup_st(something):

        globals()["%s_lock" % something[:-6]].acquire()
        if len(globals()[something]) > cleanup_thres:
            globals()["%s_lock" % something[:-6]].release()

            with globals()["%s_lock" % something[:-6]]:
                n = int(len(globals()[something])*0.1)

            for key in globals()[something].copy():
                if n > 0:
                    with globals()["%s_lock" % something[:-6]]:
                        try:
                            globals()[something].pop(key)
                        except TypeError:
                            globals()[something].remove(key)
                else:
                    break
                n -= 1
        else:
            globals()["%s_lock" % something[:-6]].release()

    print("cleaning up...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        for something in somethings:
            executor.submit(cleanup_st, something)
    dump_mt(*somethings)


if __name__ == "__main__":
    while 1:
        acq_datetime()
        print("\n", "fresh new round at %s %s" % (date, time))

        r_del_old()

        print("loading list of downloaded, pending and stashed articles...")
        load_mt("downloaded_artls", "pending_artls", "stashed_artls")

        retry = False
        if pending_artls:
            retry = True
            print("%d article(s) pending, will retry..." % len(pending_artls))
        else:
            print("no pending articles")

        temp_stashed = [value for value in stashed_artls.values()
                        if type(value) == tuple and value[0] <= stashed_retry]
        if temp_stashed:
            retry = True
            print("%d article(s) stashed, will retry..." % len(temp_stashed))
        else:
            print("no stashed articles")

        if retry:
            print("retrying...")
            download_artls_mt(pending_artls, stashed_artls)

        # read list of sites from file
        print("loading sites to parse...")
        with open(cwpath+"sites.txt", "r") as f:
            sites = [line.split("\t") for line in f.read().split("\n")[:-1]]
        extr_src_mt(sites)

        r_mput()

        cleanup_mt("downloaded_artls", "stashed_artls", "pending_artls")
