#!/usr/bin/python
# -*- coding: utf-8 -*-
from subprocess import call


rmapi_loc = "go run github.com/juruen/rmapi"


def rmapi(*cmd):
    call("echo 'cd pdt \nls' | "+rmapi_loc, shell=True)


if __name__ == "__main__":
    rmapi()
