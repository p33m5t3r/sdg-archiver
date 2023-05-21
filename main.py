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
    def __init__(self, outdir, ratelimit=None):
        self.loglvl = NORMAL

        self.img_path = outdir

        if not os.path.exists(self.img_path):
            os.makedirs(self.img_path)

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
        if url.split('.')[-1] == "webm":
            self.log(f"skipping .webm file...", NORMAL)
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

    def get_archive_threadnos(self, board: str) -> list[int]:
        res = requests.get(JSON_URL + f"/{board}/archive.json").json()
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


def get_img_url(board: str, post: dict) -> str:
    return IMG_URL + f'/{board}' + f'/{post.get("tim")}' + post.get("ext")


def has_img(post: dict) -> bool:
    return post.get("filename") is not None


def include_img(post: dict) -> bool:
    # put optional image inclusion logic here (maybe DL thumbnail and decide to keep or not)
    return True


def get_thread_no(thread: list[dict]) -> int:
    return thread[0].get("no")


def get_img_urls_from_thread(board: str, thread: list[dict]) -> list[str]:
    return list(map(lambda post: get_img_url(board, post), filter(include_img, filter(has_img, thread))))


def get_seen_threadnos() -> list[int]:
    with open('thread_cache.json', 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            data = []

    return [thread[0].get("no") for thread in data if thread and thread[0]]


# adds a thread to thread_cache if it's not there already.
# returns true if a new unique thread was cached
def cache_thread(thread: list[dict]) -> bool:
    # Check if thread_cache.json exists, if not, create one.
    if not os.path.isfile('thread_cache.json'):
        with open('thread_cache.json', 'w') as f:
            json.dump([], f)

    threadnos = get_seen_threadnos()
    if get_thread_no(thread) in threadnos:
        return False

    with open('thread_cache.json', 'r') as json_file:
        try:
            data = json.load(json_file)
        except json.JSONDecodeError:
            data = []

    # Append new threads to existing data
    data.append(thread)

    # Write back to the file
    with open('thread_cache.json', 'w') as json_file:
        json.dump(data, json_file)

    return True


# returns the number of new threads that were cached
def cache_threads(threads: list[list[dict]]) -> (int, int):
    s = 0
    for thread in threads:
        s += 1 if cache_thread(thread) else 0
    return s


def find_matching(_board: str, _pattern: str, api: Api, _tries=None, _count=None) -> list[list[dict]]:
    print(f"looking for threads in {_board} with title containing {_pattern}")
    try_str = "" if _tries is None else f"will try {_tries} archive entries..."
    count_str = "" if _count is None else f"will stop when found {_count} matching threads..."
    print(try_str)
    print(count_str)
    print("="*20)
    sdg_threads = []
    archive = api.get_archive_threadnos(_board)
    if _tries is None:
        _tries = len(archive)
    archive.sort(reverse=True)
    seen_threadnos = get_seen_threadnos()
    try:
        for index, thread_no in enumerate(archive[:_tries]):
            if thread_no in seen_threadnos:
                print(f"thread #{thread_no} has already been cached or downloaded. Skipping.")
                continue
            thread = api.get_thread(_board, thread_no)
            matches = get_thread_name(thread).__contains__(_pattern)
            match_str = "\t\t\t ***MATCH***" if matches else ""
            api.log(f"{index}: {thread_no} -> {get_thread_name(thread)} {match_str}", NORMAL)

            if matches:
                cache_thread(thread)
                sdg_threads.append(thread)

            if _count and len(sdg_threads) >= _count:
                return sdg_threads
    except KeyboardInterrupt:
        pass

    return sdg_threads


# side effect: removes items from cache that have been seen aka fully downloaded
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

    # read contents of thread_cache into cache
    with open('thread_cache.json', 'r') as json_file:
        try:
            cache = json.load(json_file)
        except json.JSONDecodeError:
            cache = []

    buf = []
    for item in cache:
        if get_thread_no(item) not in data:
            buf.append(item)

    to_be_purged = list(map(get_thread_no, [c for c in cache if c not in buf]))

    # effectively removes the no-longer-needed items in cache
    with open('thread_cache.json', 'w') as json_file:
        try:
            json.dump(buf, json_file)
            print(f"purged {len(to_be_purged)} items from cache: {to_be_purged}")
        except json.JSONDecodeError:
            print("failed to clear cache")


def pop_thread_cache() -> list[list[dict]]:
    with open('thread_cache.json', 'r') as json_file:
        sdg_threads_json = json_file.read()

    return json.loads(sdg_threads_json)


def download_from_threads(api: Api, board: str, threads: list[list[dict]]):
    total_img_count = sum(1 for thread in threads for post in thread if has_img(post))

    progress = 0
    for i, thread in enumerate(threads):
        thread_no = thread[0].get("no")
        urls = get_img_urls_from_thread(board, thread)
        api.log(f"downloading {len(urls)} files from thread {i+1}/{len(threads)}", NORMAL)
        for url in urls:
            progress += 1
            path = api.img_url_to_path(url)
            if not os.path.exists(path):
                print(f"[{progress}/{total_img_count}] ", end="")
                api.queue_download(url)
            else:
                api.log(f"file {path} already exists, skipping...", NORMAL)

        api.log(f"%%%%% FULLY DOWNLOADED thread: {thread_no} %%%%%%", NORMAL)
        # once fully downloaded, mark the thread as seen
        mark_thread_as_seen(thread_no)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrapes stable diffusion general threads")
    parser.add_argument('-outdir', type=str, default="sdg", help="folder to store images in")
    parser.add_argument('-pattern', type=str, default="/sdg/", help="what to look for in thread title to determine"
                                                                    "whether or not to download its images")
    parser.add_argument('-board', type=str, default="g", help="board to search in")

    # threads are cached by default as the download process runs in case of an unexpected exit
    parser.add_argument('--cache', action="store_true", default=False, help='ONLY cache, but do not download,'
                                                                            ' threads for later processing')
    parser.add_argument('--pop', action="store_true", default=False, help='download from cached threads')
    parser.add_argument('--count', type=int, default=1, help='keep pulling threads from archive until N '
                                                             'matching threads found. default=1')
    parser.add_argument('--tries', type=int, default=0, help='go by attempts at finding matches in the archive, '
                                                             'rather than successes. useful if you want to try to'
                                                             'download the entire archive')

    parser.add_argument('--inspect', action="store_true", default=False, help='inspect the current cache')

    args = parser.parse_args()

    if args.inspect:
        cache = pop_thread_cache()
        threadnos = list(map(get_thread_no, cache))
        if threadnos:
            print(f"found ({len(threadnos)}) threads: {threadnos} in cache.")
            exit(0)
        else:
            print("cache is empty.")

    if args.cache and args.pop:
        print("you called the program with --cache and --pop (this does nothing) so the program will exit now.")
        exit(0)

    # if we want a minimum number of threads, don't stop trying until we hit said count
    tries = None if args.tries == 0 else args.tries
    board = args.board
    pattern = args.pattern
    api = Api(outdir=args.outdir, ratelimit=1)

    if args.pop:
        target_threads = pop_thread_cache()
        api.log(f"found {len(target_threads)} threads to download from cache.", NORMAL)
    else:
        target_threads = find_matching(board, pattern, api, tries, args.count)
        api.log("="*20, NORMAL)
        api.log(f"found {len(target_threads)} matching threads in /{board}/ archive...", NORMAL)

    if args.cache:
        successes = cache_threads(target_threads)
        api.log(f"cached {successes} new threads, found {len(target_threads) - successes} "
                f"duplicates sitting in cache", NORMAL)
    else:
        download_from_threads(api, board, target_threads)
        api.log("done :3", NORMAL)







