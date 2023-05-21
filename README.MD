# 4chan SDG scraper


### about:
I wrote this very quickly in an afternoon so there's plenty of spaghetti, but most things should be very reusable if you
want to adapt this to your board/thread of choice.

## usage:

EXAMPLE:


`python main.py -board="h" -outdir="hdg" -pattern="/hdg/" --count=2`
will find the first two threads in the catalog of the board "/h" whose title contains the string "/hdg/", and will 
download every image in both threads, and save them in a new folder called "hdg" in the current working directory. 

---

`python main.py` will comb the ~first 500 entries of the /g/ archive for stable diffusion threads and download 
the full-sized images to a new folder named "sdg".

`python main.py --cache` will do the same but won't download the images, instead, the threads will be saved in 
"thread_cache.json".

`python main.py --pop` will download all the images in your local cache (the cache only holds the URLs, the actual
images are still on the 4chan servers until you run this command to download them to your machine)

`python main.py <flags> --tries=1000` will look for threads in the first 1000 entries of the archive

`python main.py <flags> --count=5` will pull thread headers from the archive until it finds 5 matching threads,
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
---

4chan internal api or whatever works just fine, no need for scraping:

[https://github.com/4chan/4chan-API](https://github.com/4chan/4chan-API)

get archive of /g/ with:

```
https://a.4cdn.org/g/archive.json
```

get thread #93545157 in /g/ with:

```
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