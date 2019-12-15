#!/usr/bin/python
# -*- coding: utf-8 -*-
from subprocess import Popen, PIPE
import re


rmapi_loc = "go run github.com/juruen/rmapi"


def rmapi(*cmds):
    return Popen("echo '%s' | %s" % ("\n".join(cmds), rmapi_loc), stdout=PIPE, shell=True).stdout.read()


if __name__ == "__main__":
    print(rmapi("ls", "cd psdt", "ls"))
