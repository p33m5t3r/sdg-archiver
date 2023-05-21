import requests
import json
import time
import urllib.request
import os
import argparse

# 4chan api
JSON_URL = "http://a.4cdn.org"
IMG_URL = "http://i.4cdn.org"

# logging lvls (I have random print statements in places so don't expect this to really do that much)
DEBUG = 2
NORMAL = 1
SILENT = 0


# the functions that actually make requests go in this class
# .. so we can optionally track state and respect the rate-limiter
class Api:
    def __init__(self, ratelimit=None):
        self.loglvl = NORMAL
        self.img_path = "archive"
        if not os.path.exists('archive'):
            os.makedirs('archive')

        if ratelimit is None:
            self.ratelimit = 1
        else:
            self.ratelimit = ratelimit
        self.last_request_t = time.time() - self.ratelimit
        self.num_requests = 0
    
    def log(self, msg, lvl: int):
        if lvl <= self.loglvl:
            print(msg)

    def img_url_to_path(self, url):
        return os.path.join(self.img_path, url.split('/')[-1])

    def download_img(self, url):
        path = self.img_url_to_path(url)
        try:
            local_file_path, headers = urllib.request.urlretrieve(url, path)
            self.log(f"Successfully downloaded {url} to {local_file_path}", NORMAL)
            # You can also log headers info if needed.
        except IOError:
            self.log(f"Failed to download {url}", NORMAL)

    def queue_download(self, url: str):
        self.num_requests += 1
        t_now = time.time()
        if not self.ratelimit:
            return self.download_img(url)

        if t_now - self.last_request_t > self.ratelimit:
            self.last_request_t = t_now
            return self.download_img(url)
        else:
            wait_time = self.ratelimit - (t_now - self.last_request_t)
            time.sleep(wait_time)
            return self.download_img(url)

    def get_catalog(self, board: str) -> list[int]:
        catalog_endpoint = f"/{board}/archive.json"
        res = requests.get(JSON_URL + catalog_endpoint).json()
        self.log(res, DEBUG)
        return res

    def get_thread(self, board: str, thread_no: int) -> list[dict]:
        response = requests.get(JSON_URL + f"/{board}/thread/{thread_no}.json")
        if response.status_code == 200:
            res = response.json().get("posts")
            self.log(res, DEBUG)
            return res if res is not None else [{}]
        else:
            return [{}]


# mostly-pure functions to manipulate, filter, etc on threads once in memory are below
def get_thread_name(thread: list[dict]) -> str:
    ret = thread[0].get("sub") if thread[0].get("sub") is not None else "untitled"
    # Api.log(f"got thread: {ret}")
    return ret


def thread_is_sdg(thread: list[dict]) -> bool:
    return get_thread_name(thread).__contains__("/sdg/")


def get_img_url(board: str, post: dict) -> str:
    return IMG_URL + f'/{board}' + f'/{post.get("tim")}' + post.get("ext")


def has_img(post: dict) -> bool:
    return post.get("filename") is not None


def include_img(post: dict) -> bool:
    # put optional image inclusion logic here (maybe DL thumbnail and decide to keep or not)
    return True


def get_img_urls_from_thread(board: str, thread: list[dict]) -> list[str]:
    return list(map(lambda post: get_img_url(board, post), filter(include_img, filter(has_img, thread))))


def get_seen_threadnos() -> list[int]:
    with open('thread_cache.json', 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            data = []

    return [thread[0].get("no") for thread in data if thread and thread[0]]


def get_sdg_threads(api: Api, t=None, c=None) -> list[list[dict]]:
    sdg_threads = []
    catalog = api.get_catalog("g")
    if t is None or c:
        t = len(catalog)
    catalog.sort(reverse=True)
    seen_threadnos = get_seen_threadnos()
    try:
        for index, thread_no in enumerate(catalog[:t]):
            if thread_no in seen_threadnos:
                print(f"thread #{thread_no} has already been cached or downloaded. Skipping.")
                continue
            thread = api.get_thread(board, thread_no)
            is_sdg = thread_is_sdg(thread)
            match_str = "\t\t\t ***MATCH***" if is_sdg else ""
            api.log(f"{index}: {thread_no} -> {get_thread_name(thread)} {match_str}", NORMAL)
            if is_sdg:
                sdg_threads.append(thread)
            if c and len(sdg_threads) >= c:
                return sdg_threads
    except KeyboardInterrupt:
        pass

    return sdg_threads


# returns number of (new, duplicate) threads
def cache_threads(threads: list[list[dict]]) -> (int, int):
    # Check if thread_cache.json exists, if not, create one.
    if not os.path.isfile('thread_cache.json'):
        with open('thread_cache.json', 'w') as f:
            json.dump([], f)

    threadnos = get_seen_threadnos()
    new_threads = list(filter(lambda t: t[0].get("no") not in threadnos, threads))

    with open('thread_cache.json', 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            data = []

    # Append new threads to existing data
    data.extend(new_threads)

    # Write back to the file
    with open('thread_cache.json', 'w') as json_file:
        json.dump(data, json_file)

    return len(new_threads), len(threads) - len(new_threads)


def mark_thread_as_seen(threadno: int):
    if not os.path.isfile('seen_threads.json'):
        with open('seen_threads.json', 'w') as f:
            json.dump([], f)

    # Load existing data
    with open('seen_threads.json', 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            data = []

    # Append new threads to existing data
    data.append(threadno)

    # Write back to the file
    with open('seen_threads.json', 'w') as json_file:
        json.dump(data, json_file)


def pop_thread_cache() -> list[list[dict]]:
    with open('thread_cache.json', 'r') as json_file:
        sdg_threads_json = json_file.read()

    return json.loads(sdg_threads_json)


def download_from_threads(api: Api, board: str, threads: list[list[dict]]):
    total_img_count = sum(1 for thread in threads for post in thread if has_img(post))

    for thread in threads:
        thread_no = thread[0].get("no")
        urls = get_img_urls_from_thread(board, thread)
        api.log(f"downloading {len(urls)} files.", NORMAL)
        for i, url in enumerate(urls):
            path = api.img_url_to_path(url)
            if not os.path.exists(path):
                print(f"[{i}/{total_img_count}] ", end="")
                api.queue_download(url)
            else:
                api.log(f"file {path} already exists, skipping...", NORMAL)

        # once done downloading, mark the thread as seen
        mark_thread_as_seen(thread_no)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrapes stable diffusion general threads")
    parser.add_argument('--cache', action="store_true", default=False, help='cache, but not download,'
                                                                            ' threads for later processing')
    parser.add_argument('--pop', action="store_true", default=False, help='download from cached threads')
    parser.add_argument('--tries', type=int, default=500, help='how many archive threads to check. defaults to 500')
    parser.add_argument('--count', type=int, default=0, help='keep pulling threads from archive until N '
                                                                      '/sdg/ threads found')
    args = parser.parse_args()

    if args.cache and args.pop:
        print("you called the program with --cache and --pop, the program will exit now.")
        exit(0)

    # if we want a minimum number of threads, don't stop trying until we hit said count
    tries = None if args.count else args.tries
    board = "g"
    api = Api(ratelimit=1)

    if args.pop:
        target_threads = pop_thread_cache()
    else:
        target_threads = get_sdg_threads(api, tries, args.count)

    # I stopped trying to generalize at some point which is why dumb stuff like this exists
    api.log(f"found {len(target_threads)} SDG threads in /{board}/ archive...", NORMAL)

    if args.cache:
        new, duplicates = cache_threads(target_threads)
        api.log(f"cached {new} new threads, found {duplicates} duplicates sitting in cache", NORMAL)
    else:
        download_from_threads(api, board, target_threads)
        api.log("done :3", NORMAL)







