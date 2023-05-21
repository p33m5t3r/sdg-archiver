# 4chan SDG scraper


### about:
I wrote this very quickly in an afternoon so there's plenty of spaghetti, but most things should be very reusable if you
want to adapt this to your board/thread of choice.

### usage:
`python main.py` will comb the ~first 500 entries of the /g/ archive for stable diffusion threads and download 
the full-sized images to the archive folder.
`python main.py --cache` will do the same but won't download the images, instead, the threads will be saved in 
"thread_cache.json".

`python main.py --pop` will download all the images in your local cache (the cache only holds the URLs, the actual
images are still on the 4chan servers until you run this command to download them to your machine)

`python main.py <flags> --tries=1000` will look for /sdg/ threads in the first 1000 entries of the archive

`python main.py <flags> --count=5` will pull thread headers from the /g/ archive until it finds 5 /sdg/ threads,
and then it will either cache or download them depending on what `<flags>` you have set.

### internals
presumably if you want to do image pruning (remove stray pepes or whatever) you can do that after using this tool for
a first-pass. but if you want to be more efficient, the threads at some point are filtered through this easily changable
function:

```python
def include_img(post: dict) -> bool:
    # put optional image inclusion logic here (maybe DL thumbnail and decide to keep or not)
    return True
```

I kind of went back and forth between wanting to generalize and not caring, so if you want to throw this on a more...
hardcore... forum, you can change this:
```python
def thread_is_sdg(thread: list[dict]) -> bool:
    return get_thread_name(thread).__contains__("/obscene hentai general or whatever/")
```

and then edit random hardcoded usages (sorry lol) of the board identifier "g" with "h" or "d" or whatever ur coomer heart desires.

---

4chan internal api or whatever works lol, i don't know why anyone would pain themselves with beautifulsoup.
[https://github.com/4chan/4chan-API](https://github.com/4chan/4chan-API)

get archive of /g/ with:

```json
https://a.4cdn.org/g/archive.json
```

get thread #93545157 in /g/ with:

```json
https://a.4cdn.org/g/thread/93545157.json
```

JSON structure

```json
{
  "posts": [
    {
      "no": 93545157,
      "closed": 1,
      "now": "05/20/23(Sat)01:07:47",
      "name": "Anonymous",
			"sub": "/sdg/ - Stable Diffusion General",
...

{
      "no": 93545165,
      "now": "05/20/23(Sat)01:08:37",
      "name": "Anonymous",
      "filename": "00047-264753980",
      "ext": ".png",
      "w": 1216,
      "h": 2000,
      "tn_w": 76,
      "tn_h": 125,
      "tim": 1684559317608662,
      "time": 1684559317,
      "md5": "5eoW35eMOfvCclbvqRFi9g==",
      "fsize": 2814870,
      "resto": 93545157
    },
```

super basic way to grab stuff from 4chan if you want to get started on your own version of this.

```python
import json
img_server_addr = "https://i.4cdn.org/g/"

posts = json.loads(request.get("https://a.4cdn.org/g/thread/93545157.json")).get("posts")
thread_title = posts[0].get("sub")

n = 123
has_img = posts[n].get("filename") is not None
if has_img:
	img_number = posts[n].get("tim")
	file_ext = posts[n].get("ext")
	img_url = img_server_addr + img_number + file_ext
	thumbnail_url = img_server_addr + img_number + "s" + file_ext
```
