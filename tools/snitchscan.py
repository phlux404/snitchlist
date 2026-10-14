#!/usr/bin/env python3
"""SnitchScan — headless SnitchList pipeline for the Debian box.

Fetches NextDNS DNS logs, runs SnitchList zero-day analysis (DB + entropy +
SDK/ASN fingerprinting), writes a markdown report to Nextcloud Notes.

Runs on the Debian box via cron. All stdlib, no dependencies.

Config:
  ~/.config/nextdns/api_key    (chmod 600) — NextDNS API key
  Uses ~/bin/ncnotes.py for Nextcloud Notes (shares ncnotify config).

Usage:
  snitchscan.py [--hours 24] [--profile <profile_id>] [--dry-run]

  Profile ID can also be set via ~/.config/nextdns/profile_id
"""
import os, sys, re, json, math, argparse
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
API_KEY_FILE = os.path.join(HOME, ".config", "nextdns", "api_key")
NOTES_DIR = "/mnt/data/next-drive/Notes"
API = "https://api.nextdns.io"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"

# ---- SnitchList DB (mirrored from index.html 2026-10-12) ----
DB = [
["t.uptodown.app","Uptodown","tracking"],
["inmobi.com","InMobi","ads"],
["inmobi-choice.io","InMobi","consent"],
["bat.bing.com","Microsoft","ads"],
["clarity.ms","Microsoft","analytics"],
["pixel-config.reddit.com","Reddit","ads"],
["alb.reddit.com","Reddit","ads"],
["firebaselogging.googleapis.com","Google","analytics"],
["firebaselogging-pa.googleapis.com","Google","analytics"],
["firebaseinstallations.googleapis.com","Google","analytics"],
["firebase-settings.crashlytics.com","Google","crash"],
["doubleclick.net","Google","ads"],
["googlesyndication.com","Google","ads"],
["googleadservices.com","Google","ads"],
["google-analytics.com","Google","analytics"],
["googletagmanager.com","Google","analytics"],
["app-measurement.com","Google","analytics"],
["admob.com","Google","ads"],
["adsense.com","Google","ads"],
["adservice.google.com","Google","ads"],
["crashlytics.com","Google","crash"],
["graph.facebook.com","Meta","social"],
["connect.facebook.net","Meta","social"],
["facebook.net","Meta","social"],
["b-www.facebook.com","Meta","social"],
["analytics.facebook.com","Meta","analytics"],
["hatch-api.meta.ai","Meta","functional"],
["hatch.metaaivm.com","Meta","functional"],
["shortwave.facebook.com","Meta","functional"],
["applovin.com","AppLovin","ads"],
["unityads.unity3d.com","Unity","ads"],
["ironsrc.com","ironSource","ads"],
["supersonicads.com","ironSource","ads"],
["vungle.com","Liftoff","ads"],
["chartboost.com","Chartboost","ads"],
["criteo.com","Criteo","ads"],
["amazon-adsystem.com","Amazon","ads"],
["aax.amazon-adsystem.com","Amazon","ads"],
["sentry.io","Sentry","crash"],
["mixpanel.com","Mixpanel","analytics"],
["amplitude.com","Amplitude","analytics"],
["segment.io","Segment","analytics"],
["cdn.segment.com","Segment","analytics"],
["branch.io","Branch","analytics"],
["appsflyer.com","AppsFlyer","tracking"],
["adjust.com","Adjust","tracking"],
["kochava.com","Kochava","tracking"],
["singular.net","Singular","tracking"],
["tenjin.com","Tenjin","tracking"],
["newrelic.com","New Relic","analytics"],
["hotjar.com","Hotjar","analytics"],
["fullstory.com","FullStory","analytics"],
["tealiumiq.com","Tealium","tracking"],
["optimizely.com","Optimizely","analytics"],
["onesignal.com","OneSignal","tracking"],
["pendo.io","Pendo","analytics"],
["intercom.io","Intercom","functional"],
["intercomcdn.com","Intercom","functional"],
["analytics.tiktok.com","TikTok","analytics"],
["sc-analytics.appspot.com","Snap","analytics"],
["ads-twitter.com","X","ads"],
["analytics.twitter.com","X","analytics"],
["ads.linkedin.com","LinkedIn","ads"],
["px.ads.linkedin.com","LinkedIn","ads"],
["analytics.pinterest.com","Pinterest","analytics"],
["scorecardresearch.com","Comscore","analytics"],
["quantserve.com","Quantcast","analytics"],
["quantcast.com","Quantcast","analytics"],
["imrworldwide.com","Nielsen","analytics"],
["bluekai.com","Oracle","tracking"],
["eloqua.com","Oracle","tracking"],
["pardot.com","Salesforce","tracking"],
["demdex.net","Adobe","tracking"],
["omtrdc.net","Adobe","analytics"],
["everesttech.net","Adobe","tracking"],
["adsrvr.org","The Trade Desk","ads"],
["mathtag.com","MediaMath","ads"],
["pubmatic.com","PubMatic","ads"],
["rubiconproject.com","Rubicon","ads"],
["openx.net","OpenX","ads"],
["casalemedia.com","Index Exchange","ads"],
["adnxs.com","AppNexus","ads"],
["outbrain.com","Outbrain","ads"],
["taboola.com","Taboola","ads"],
["revcontent.com","Revcontent","ads"],
["doubleverify.com","DoubleVerify","tracking"],
["adsafeprotected.com","Integral Ad Science","tracking"],
["moatads.com","Oracle","tracking"],
["samsungads.com","Samsung","ads"],
["config.samsungads.com","Samsung","ads"],
["mistat.xiaomi.com","Xiaomi","analytics"],
["data.mistat.xiaomi.com","Xiaomi","analytics"],
["tracking.miui.com","Xiaomi","analytics"],
["nextdns.io","NextDNS","functional"],
["metrics.apple.com","Apple","analytics"],
]

ENTROPY_THRESHOLD = 3.5  # calibrated 2026-10-12, FP 3.0%

SDK_PATTERNS = [
    (r"^firebase[a-z0-9-]*\.", "Firebase"),
    (r"crashlytics", "Crashlytics"),
    (r"^app-measurement", "Firebase Analytics"),
    (r"appsflyer", "AppsFlyer"),
    (r"\.branch\.io$", "Branch"),
    (r"segment", "Segment"),
    (r"amplitude", "Amplitude"),
    (r"mixpanel", "MixPanel"),
    (r"\.onesignal\.com$", "OneSignal"),
    (r"kochava", "Kochava"),
    (r"adjust\.", "Adjust"),
    (r"\.ironsrc\.com$", "ironSource"),
    (r"applovin", "AppLovin"),
    (r"\.vungle\.com$", "Vungle"),
    (r"chartboost", "Chartboost"),
    (r"\.criteo\.com$", "Criteo"),
    (r"tealium", "Tealium"),
    (r"\.pendo\.io$", "Pendo"),
    (r"hotjar", "Hotjar"),
    (r"fullstory", "FullStory"),
    (r"\.intercom", "Intercom"),
]
SDK_PATTERNS = [(re.compile(p, re.I), name) for p, name in SDK_PATTERNS]

SUSPICIOUS_TLDS = {"xyz", "top", "biz", "info", "click", "link"}

# ---- analysis ----

def shannon(s):
    if not s: return 0.0
    from collections import Counter
    c = Counter(s)
    n = len(s)
    return -sum((v/n) * math.log2(v/n) for v in c.values())

def domain_entropy(domain):
    parts = domain.lower().split(".")
    if len(parts) < 2: return 0.0
    return shannon("".join(parts[:-1]))

def lookup(domain):
    for suf, company, cat in DB:
        if domain == suf or domain.endswith("." + suf):
            return company, cat, suf
    return None

def analyze_signals(domain):
    signals = []
    lower = domain.lower()
    ent = domain_entropy(domain)
    if ent >= ENTROPY_THRESHOLD:
        signals.append(("high-entropy",
            f"entropy {ent:.2f} bits >= threshold {ENTROPY_THRESHOLD} (calibrated FP 3.0%)",
            "medium"))
    for pat, name in SDK_PATTERNS:
        if pat.search(lower):
            signals.append(("sdk-match", f"matches {name} SDK pattern", "high"))
            break
    labels = lower.split(".")
    if len(labels) >= 4:
        signals.append(("deep-subdomain",
            f"{len(labels)} labels deep; trackers use deep subdomains for data exfil", "low"))
    label_str = "".join(labels[:-1])
    if label_str:
        digit_ratio = sum(1 for c in label_str if c.isdigit()) / len(label_str)
        if digit_ratio > 0.3 and len(label_str) > 8:
            signals.append(("numeric-heavy",
                f"{digit_ratio*100:.0f}% digits in labels; generated domains skew numeric", "low"))
    if labels[-1] in SUSPICIOUS_TLDS:
        signals.append(("suspicious-tld",
            f"TLD .{labels[-1]} is disproportionately abused by trackers", "low"))
    return signals

# ---- NextDNS API ----

def api_get(path, api_key):
    r = urllib.request.Request(API + path)
    r.add_header("X-Api-Key", api_key)
    r.add_header("User-Agent", UA)
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())

def fetch_logs(api_key, profile_id, hours):
    now = datetime.now(timezone.utc)
    frm = str(int((now - timedelta(hours=hours)).timestamp()))
    to = str(int(now.timestamp()))
    entries = []
    cursor = None
    while True:
        qs = f"from={frm}&to={to}&limit=1000&sort=desc"
        if cursor: qs += f"&cursor={cursor}"
        data = api_get(f"/profiles/{profile_id}/logs?{qs}", api_key)
        entries.extend(data.get("data", []))
        cursor = (data.get("meta") or {}).get("pagination", {}).get("cursor")
        if not cursor: break
    return entries

# ---- report ----

def build_report(entries, hours):
    counts = {}
    for e in entries:
        d = e.get("domain", "").lower().rstrip(".")
        if not d or re.match(r"^\d+\.\d+\.\d+\.\d+$", d): continue
        counts[d] = counts.get(d, 0) + 1

    snitches, unknowns, clean = [], [], []
    companies = {}
    for domain, hits in sorted(counts.items(), key=lambda x: -x[1]):
        hit = lookup(domain)
        if hit:
            company, cat, _ = hit
            if cat == "functional":
                clean.append((domain, hits, f"{company} infrastructure"))
            else:
                snitches.append((domain, hits, company, cat))
                c = companies.setdefault(company, [0, 0])
                c[0] += 1; c[1] += hits
        else:
            signals = analyze_signals(domain)
            unknowns.append((domain, hits, signals))

    flagged = [(d, h, s) for d, h, s in unknowns if s]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date_short = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    r = f"# SnitchScan report — {date_short}\n\n"
    r += f"Automated DNS log analysis, last {hours}h. Generated {now}.\n\n"
    r += f"- Total DNS hits: {sum(counts.values())}\n"
    r += f"- Unique domains: {len(counts)}\n"
    r += f"- Snitch domains: {len(snitches)}\n"
    r += f"- Unknown: {len(unknowns)} ({len(flagged)} with tracker signals)\n"
    r += f"- Clean/functional: {len(clean)}\n\n"

    r += "## Snitches\n"
    for d, h, co, cat in snitches[:50]:
        r += f"- {d} ({h} hits) — {co} [{cat}]\n"
    if len(snitches) > 50: r += f"- ... and {len(snitches)-50} more\n"

    r += "\n## Flagged unknowns (zero-day signals)\n"
    if flagged:
        for d, h, sigs in sorted(flagged, key=lambda x: -x[1])[:30]:
            sig_str = "; ".join(f"{s[0]}: {s[1]}" for s in sigs)
            r += f"- **{d}** ({h} hits) — {sig_str}\n"
    else:
        r += "None. All unknowns look clean.\n"

    r += "\n## Company rollup\n"
    for co, (nd, h) in sorted(companies.items(), key=lambda x: -x[1][1])[:20]:
        r += f"- {co}: {nd} domains, {h} hits\n"

    r += "\n## Other unknowns\n"
    other = [(d, h) for d, h, s in unknowns if not s]
    for d, h in other[:20]:
        r += f"- {d} ({h} hits)\n"
    if len(other) > 20: r += f"- ... and {len(other)-20} more\n"

    return r, date_short

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--profile", default=None,
                    help="NextDNS profile ID (or set ~/.config/nextdns/profile_id)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--notes-title", default=None)
    args = ap.parse_args()

    # Profile ID from arg, config file, or fail
    profile_id = args.profile
    if not profile_id:
        pid_file = os.path.join(HOME, ".config", "nextdns", "profile_id")
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                profile_id = f.read().strip()
    if not profile_id:
        print("No profile ID: pass --profile or create ~/.config/nextdns/profile_id",
              file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(API_KEY_FILE):
        print(f"Missing {API_KEY_FILE} — create it with your NextDNS API key (chmod 600)",
              file=sys.stderr)
        sys.exit(1)
    with open(API_KEY_FILE) as f:
        api_key = f.read().strip()

    print(f"Fetching {args.hours}h of logs...", file=sys.stderr)
    entries = fetch_logs(api_key, profile_id, args.hours)
    print(f"Got {len(entries)} log entries", file=sys.stderr)

    report, date_short = build_report(entries, args.hours)

    if args.dry_run:
        print(report)
        return

    title = args.notes_title or f"SnitchScan {date_short}"
    # Write directly to Nextcloud Notes sync folder
    if not os.path.isdir(NOTES_DIR):
        print(f"Notes dir not found: {NOTES_DIR}", file=sys.stderr)
        print(report)
        sys.exit(1)
    # Sanitize title for filename
    safe = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '-')
    out_path = os.path.join(NOTES_DIR, f"{safe}.md")
    with open(out_path, 'w') as f:
        f.write(report)
    print(f"Wrote: {out_path}", file=sys.stderr)

if __name__ == "__main__":
    main()
