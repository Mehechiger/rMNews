#!/usr/bin/python3
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
import newspaper
import pdfkit
import os
from collections import defaultdict
from datetime import datetime


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
date = time = None  # date and time
retry = 50  # max time of download retry


def path_check(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def acq_datetime():
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


def extr_src(lan, site_name, site_url):
    """
    to be separated into extr_src() and download_artl()
    """
    src = newspaper.build(site_url, language=lan, memoize_articles=False)
    """
    write src.articles to file for failsafe
    """
    for artl in src.articles:
        try:
            artl.download()
            artl.parse()
        except:
            print("error, passed")
            continue
        if saveas_pdf("%s %s" % (time, artl.title), artl.url, "%s/downloaded/%s %s/" % (rpath, date, site_name)):
            print("%s %s downloaded" % (time, artl.title))
        else:
            stashed_artls[("%s %s" % (time, artl.title), artl.url, site_name)]
            print("%s %s stashed" % (time, artl.title))


def load_stashed():
    try:
        with open(rpath+"stashed_artls", "r") as f:
            stashed_artls = defaultdict(int, {tuple(line.split("\t\t")[0].split("\t")): int(line.split(
                "\t\t")[1]) for line in f.read().split("\n")[:-1] if int(line.split("\t\t")[1]) < retry})
    except FileNotFoundError:
        pass


def save_stashed():
    with open(rpath+"stashed_artls", "w") as f:
        f.write("\n".join("%s\t\t%s" % ("\t".join(k), str(v))
                          for k, v in stashed_artls.items()))


if __name__ == "__main__":
    newspaper.Config().browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'

    acq_datetime()

    # read list of sites from file
    with open(rpath+"sites.txt", "r") as f:
        sites = [line.split("\t") for line in f.read().split("\n")[:-1]]

    # read stashed articles from file
    load_stashed()

    # retry stashed articles
    for title, url, site_name in stashed_artls.copy():
        if saveas_pdf(title, url, "%s/downloaded/%s %s/" % (rpath, date, site_name)):
            stashed_artls.pop((title, url, site_name))
            print("%s downloaded" % title)
        else:
            stashed_artls[(title, url, site_name)] += 1
            print("%s stashed" % title)
    save_stashed()

    for site in sites:
        acq_datetime()
        extr_src(*site)

        # write stashed articles to file
        save_stashed()

        print(rmapi("ls", "cd psdt", "ls"))
