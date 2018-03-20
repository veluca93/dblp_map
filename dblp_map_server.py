#!/usr/bin/env python2
# pylint: disable=missing-docstring,wrong-import-position
# pylint: disable=too-many-instance-attributes,invalid-name
# pylint: disable=too-many-locals,too-many-function-args
# pylint: disable=too-many-return-statements,too-many-branches
# pylint: disable=too-many-statements,bare-except
# pylint: disable=bad-continuation

from __future__ import print_function

from collections import deque
import errno
import os
import pickle
import sys
import xml.etree.ElementTree as ET
import json
import urllib2
import urllib
import urlparse
import time
import traceback

import gevent
from gevent import monkey
monkey.patch_all()

from werkzeug.utils import redirect
from werkzeug.wsgi import SharedDataMiddleware, responder
from werkzeug.serving import run_simple
from werkzeug.exceptions import NotFound, BadRequest, TooManyRequests
from werkzeug.wrappers import Response
from googleapiclient.discovery import build

import geoip


class DBLPHandler(object):
    def __init__(self, mmdb, google_api_key, google_cs_id):
        self.search_url = "http://dblp.uni-trier.de/search/author?xauthor="
        self.person_url = "http://dblp.uni-trier.de/pers/xx/"
        self.collaborators_url = "http://dblp.uni-trier.de/pers/xc/"
        self.person_url_human = "http://dblp.uni-trier.de/pers/hd/"
        self.db = geoip.open_database(mmdb.encode('utf8'))
        self.max_cache = 10000
        self.cache = dict()
        self.cachelist = deque()
        self.lastPageLoad = time.time()
        self.google_api_key = google_api_key
        self.google_cs_id = google_cs_id
        if self.google_api_key is not None:
            self.google_cache = dict()
            with open(
                    os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "accademic_websites.txt")) as f:
                self.accademic_websites = set()
                for aw in f:
                    website = aw.strip()
                    if website.startswith('www.'):
                        website = website[4:]
                    self.accademic_websites.add(website)

    def getpage(self, url):
        if url not in self.cache:
            while time.time() < self.lastPageLoad + 0.1:
                gevent.sleep(0.01)
            self.lastPageLoad = time.time()
            opener = urllib2.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
            page = opener.open(url).read()
            self.cachelist.append(url)
            self.cache[url] = page
            if len(self.cache) > self.max_cache:
                del self.cache[self.cachelist.popleft()]
        return self.cache[url]

    def is_accademic(self, host):
        host_split = host.split('.')
        if host_split[0] == 'dblp':
            return False
        for l in range(len(host_split)):
            test = ".".join(host_split[l:])
            if test in self.accademic_websites:
                return True
        return False

    def do_google_query(self, who):
        cachedir = os.path.join(os.path.dirname(__file__), 'google_cache')
        cachefile = os.path.join(cachedir, urllib.quote(who))
        if not os.path.exists(cachefile):
            try:
                os.makedirs(cachedir)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
            service = build(
                "customsearch", "v1", developerKey=self.google_api_key)
            res = service.cse().list(q=who, cx=self.google_cs_id).execute()
            with open(cachefile, 'wb') as f:
                pickle.dump(res, f, pickle.HIGHEST_PROTOCOL)
        with open(cachefile, 'rb') as f:
            return pickle.load(f)

    def get_homepage_from_google(self, who):
        if self.google_api_key is None:
            return None
        if who not in self.google_cache:
            who_human = who.split('/')[1].replace(':', ' ')
            res = self.do_google_query(who_human)
            for url in [x.get('link') for x in res.get('items')]:
                if self.is_accademic(urlparse.urlparse(url).netloc):
                    self.google_cache[who] = url
                    break
            if who not in self.google_cache:
                self.google_cache[who] = None
        return self.google_cache[who]

    def gethostbyname(self, host):
        if host not in self.cache:
            ip = gevent.socket.gethostbyname(host)
            self.cachelist.append(host)
            self.cache[host] = ip
            if len(self.cache) > self.max_cache:
                del self.cache[self.cachelist.popleft(0)]
        return self.cache[host]

    @responder
    def __call__(self, environ, start_response):
        response = Response()
        response.mimetype = 'application/json'
        response.status_code = 200
        if environ["PATH_INFO"] == "/":
            return redirect("/index.html")
        elif environ["PATH_INFO"].startswith("/search"):
            what = environ["PATH_INFO"].split("/")
            if len(what) != 3:
                return BadRequest()
            what = urllib.quote(what[2])
            dwl = self.getpage(self.search_url + what)
            authors = ET.fromstring(dwl)
            data = []
            for a in authors:
                data.append({"name": a.text, "url": a.get("urlpt")})
            response.data = json.dumps(data)
        elif environ["PATH_INFO"].startswith("/collaborators"):
            who = environ["PATH_INFO"].split("/")
            if len(who) < 3:
                return BadRequest()
            who = "/".join(who[2:])
            if who.startswith(self.person_url_human):
                who = who[len(self.person_url_human):]
            try:
                dwl = self.getpage(self.collaborators_url + who)
            except urllib2.HTTPError as e:
                if e.code == 429:
                    return TooManyRequests()
                return NotFound()
            authors = ET.fromstring(dwl)
            data = []
            for a in authors:
                data.append({"name": a.text, "url": a.get("urlpt")})
            response.data = json.dumps(data)
        elif environ["PATH_INFO"].startswith("/geolocate"):
            who = environ["PATH_INFO"].split("/")
            if len(who) < 3:
                return BadRequest()
            who = "/".join(who[2:])
            if who.startswith(self.person_url_human):
                who = who[len(self.person_url_human):]
            try:
                dwl = self.getpage(self.person_url + who)
            except urllib2.HTTPError as e:
                if e.code == 429:
                    return TooManyRequests()
                return NotFound()
            data = ET.fromstring(dwl)
            if 'f' in data.attrib:
                who2 = data.attrib.get('f')
                print(who2)
                try:
                    dwl = self.getpage(self.person_url + who2)
                except urllib2.HTTPError as e:
                    if e.code == 429:
                        return TooManyRequests()
                    return NotFound()
                data = ET.fromstring(dwl)
            person_info = data.find("person")
            homepage = person_info.find("url")
            homepage = homepage.text if homepage is not None else None
            if homepage is None:
                homepage = self.get_homepage_from_google(who)
            if homepage is None:
                data = {"url": who}
            else:
                try:
                    domain = homepage.split("/")[2]
                    ip = self.gethostbyname(domain)
                    info = self.db.lookup(ip)
                    data = {
                        "url": who,
                        "country": info.country,
                        "subdivisions": list(info.subdivisions),
                        "coords": info.location
                    }
                except:
                    traceback.print_exc()
                    data = {"url": who}
            response.data = json.dumps(data)
        else:
            return BadRequest()
        return response


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(
            "Usage: %s address port geoipDB [google-api-key google-custom-search-id]"
            % sys.argv[0],
            file=sys.stderr)
        sys.exit(1)
    address = sys.argv[1]
    port = int(sys.argv[2])
    if len(sys.argv) > 4:
        google_api_key = sys.argv[4]
        google_cs_id = sys.argv[5]
    else:
        google_api_key = None
        google_cs_id = None
    wsgi_app = SharedDataMiddleware(
        DBLPHandler(sys.argv[3], google_api_key, google_cs_id), {'/': 'web'})
    run_simple(address, port, wsgi_app, threaded=True, use_debugger=True)
