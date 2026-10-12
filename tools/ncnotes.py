#!/usr/bin/env python3
"""ncnotes - read and write Nextcloud Notes via WebDAV.

The Nextcloud Notes app stores notes as plain markdown files in a folder
(default "Notes"). Anything written here shows up in the Notes web UI and
in sync clients like Quillpad on Android.

Python 3, standard library only - no dependencies.

Auth: same as ncnotify - a Nextcloud username + app password. Reads
~/.config/ncnotes/config first, then falls back to ~/.config/ncnotify/config
(or environment variables):

    NEXTCLOUD_URL=https://cloud.example.com
    NEXTCLOUD_USER=admin
    NEXTCLOUD_APP_PASSWORD=<your-app-password>

Optional: NOTES_PATH (default "Notes") - the folder the Notes app uses.
"""
import argparse
import base64
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

CONFIG_FILES = [
    os.path.expanduser("~/.config/ncnotes/config"),
    os.path.expanduser("~/.config/ncnotify/config"),
]


def load_config():
    cfg = {}
    for path in CONFIG_FILES:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    cfg.setdefault(k.strip(), v.strip())
        except OSError:
            continue
    return cfg


_CFG = load_config()


def setting(name, default=""):
    return os.environ.get(name, "").strip() or _CFG.get(name, default).strip()


def base_url():
    url = setting("NEXTCLOUD_URL").rstrip("/")
    if not url:
        sys.stderr.write("error: NEXTCLOUD_URL not set.\n")
        sys.exit(2)
    return url


def auth_header():
    user = setting("NEXTCLOUD_USER")
    pw = setting("NEXTCLOUD_APP_PASSWORD")
    if not user or not pw:
        sys.stderr.write("error: NEXTCLOUD_USER / NEXTCLOUD_APP_PASSWORD not set.\n")
        sys.exit(2)
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def tunnel_proxy():
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not https_proxy:
        return None
    return f"{https_proxy.rsplit(':', 1)[0]}:3130"


def is_tailnet_host(host):
    host = (host or "").lower().rstrip(".")
    if host.endswith(".ts.net"):
        return True
    parts = host.split(".")
    return (len(parts) == 4 and parts[0] == "100"
            and parts[1].isdigit() and 64 <= int(parts[1]) <= 127
            and all(p.isdigit() for p in parts))


def build_opener(url):
    host = urllib.parse.urlparse(url).hostname or ""
    if is_tailnet_host(host):
        proxy = tunnel_proxy()
        if not proxy:
            sys.stderr.write("error: tailnet host but no HTTPS_PROXY set.\n")
            sys.exit(2)
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener()


def notes_api_url(*parts):
    enc = "/".join(urllib.parse.quote(str(p), safe="") for p in parts)
    return f"{base_url()}/index.php/apps/notes/api/v1/notes/{enc}".rstrip("/")


def notes_api(method, suffix="", data=None, timeout=120):
    import json as _json
    url = notes_api_url(suffix) if suffix else f"{base_url()}/index.php/apps/notes/api/v1/notes"
    body = None
    headers = {"Authorization": auth_header(), "Accept": "application/json"}
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = build_opener(url)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, _json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:2000]
    except urllib.error.URLError as e:
        sys.stderr.write(f"error: network: {e.reason}\n")
        sys.exit(1)


def notes_list():
    status, data = notes_api("GET")
    if status != 200 or not isinstance(data, list):
        sys.stderr.write(f"error: notes API {status}\n{data}\n")
        sys.exit(1)
    return data


def find_note_id(title):
    want = title.lower()
    for n in notes_list():
        if n.get("title", "").lower() == want:
            return n["id"]
    return None


def api_get_note(title):
    """Full note dict for a title (case-insensitive), or None."""
    want = title.lower()
    for n in notes_list():
        if n.get("title", "").lower() == want:
            status, data = notes_api("GET", str(n["id"]))
            if status == 200 and isinstance(data, dict):
                return data
            return n
    return None


def api_check(status, data, action):
    if status not in (200, 201):
        sys.stderr.write(f"error: notes API {status} on {action}\n{data}\n")
        sys.exit(1)


def cmd_list(args):
    notes = notes_list()
    if args.category is not None:
        notes = [n for n in notes if (n.get("category") or "") == args.category]
    for n in sorted(notes, key=lambda x: x.get("title", "")):
        cat = n.get("category") or ""
        suffix = f"  [{cat}]" if cat and args.category is None else ""
        print(f"{n.get('title')}{suffix}")


def cmd_read(args):
    note = api_get_note(args.title)
    if note is None:
        sys.stderr.write(f"error: no such note: {args.title}\n")
        sys.exit(1)
    sys.stdout.write(note.get("content", ""))


def cmd_write(args):
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    elif args.stdin:
        text = sys.stdin.read()
    else:
        text = args.text or ""
    note = api_get_note(args.title)
    if note is not None:
        data = {"content": text, "category": note.get("category") or ""}
        if args.category is not None:
            data["category"] = args.category
        status, resp = notes_api("PUT", str(note["id"]), data)
        api_check(status, resp, "update")
    else:
        payload = {"title": args.title, "content": text}
        if args.category is not None:
            payload["category"] = args.category
        status, resp = notes_api("POST", "", payload)
        api_check(status, resp, "create")
    where = f" [category: {args.category}]" if args.category is not None else ""
    print(f"wrote note: {args.title}{where}")


def cmd_categorize(args):
    note_id = find_note_id(args.title)
    if note_id is None:
        sys.stderr.write(f"error: no such note: {args.title}\n")
        sys.exit(1)
    status, data = notes_api("PUT", str(note_id), {"category": args.category})
    if status != 200:
        sys.stderr.write(f"error: notes API {status}\n{data}\n")
        sys.exit(1)
    print(f"categorized: {args.title} -> {args.category or '(uncategorized)'}")


def cmd_delete(args):
    note = api_get_note(args.title)
    if note is None:
        sys.stderr.write(f"error: no such note: {args.title}\n")
        sys.exit(1)
    status, resp = notes_api("DELETE", str(note["id"]))
    api_check(status, resp, "delete")
    print(f"deleted note: {args.title}")


def cmd_categories(args):
    cats = sorted({n.get("category") or "" for n in notes_list()})
    for c in cats:
        print(c or "(uncategorized)")


def cmd_append(args):
    text = args.text or sys.stdin.read()
    note = api_get_note(args.title)
    if note is None:
        status, resp = notes_api("POST", "",
                                 {"title": args.title, "content": ""})
        api_check(status, resp, "create")
        note = api_get_note(args.title)
    existing = note.get("content", "")
    sep = "" if not existing or existing.endswith("\n") else "\n"
    new = existing + sep + text + ("" if text.endswith("\n") else "\n")
    status, resp = notes_api("PUT", str(note["id"]),
                             {"content": new,
                              "category": note.get("category") or ""})
    api_check(status, resp, "append")
    print(f"appended to note: {args.title}")


def main():
    ap = argparse.ArgumentParser(description="Read/write Nextcloud Notes via the Notes API.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list notes")
    p.add_argument("--category", default=None,
                   help="only list notes in this category (Quillpad notebook)")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("read", help="print a note's content")
    p.add_argument("title", help="note title")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("write", help="write (create or overwrite) a note")
    p.add_argument("title", help="note title")
    p.add_argument("--category", default=None,
                   help="set the note's category (Quillpad notebook)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("text", nargs="?", default="", help="note text")
    g.add_argument("--file", help="read note text from a file")
    g.add_argument("--stdin", action="store_true", help="read note text from stdin")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("categorize", help="move a note to a category (Quillpad notebook)")
    p.add_argument("title", help="note title")
    p.add_argument("category", nargs="?", default="",
                   help="category name (empty = uncategorized)")
    p.set_defaults(func=cmd_categorize)

    p = sub.add_parser("categories", help="list all categories")
    p.set_defaults(func=cmd_categories)

    p = sub.add_parser("delete", help="delete a note")
    p.add_argument("title", help="note title")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("append", help="append text to a note (creates it if missing)")
    p.add_argument("title", help="note title")
    p.add_argument("text", nargs="?", default="", help="text to append (or stdin)")
    p.set_defaults(func=cmd_append)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
