#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =====================================================================
#  MAHEN MUSE  -  single-file AI Song MAKER   (Flask, DevX edit)
# ---------------------------------------------------------------------
# =====================================================================
import os, sys, json, time, uuid, random, re, urllib.parse, threading, datetime, shutil
import requests
from flask import Flask, request, jsonify, Response, send_from_directory
import colorama
from colorama import Fore, Style

# UTF-8 & Windows Console setup
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
colorama.just_fix_windows_console()
colorama.init(autoreset=True, wrap=True)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ----------------------------- constants ---------------------------
FIREBASE_KEY    = "AIzaSyBasXmgMDRPnI5suMIzk2vyFx8MJMjIz9E"
FIREBASE_SIGNUP = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key=" + FIREBASE_KEY
API_BASE        = "https://xty1kppqp0.execute-api.eu-central-1.amazonaws.com/Prod"
COVER_BASE      = "https://onmusic.ai/images/covers/{job}.webp"
HERE            = os.path.dirname(os.path.abspath(__file__))
CACHE           = os.path.join(HERE, "songs")
os.makedirs(CACHE, exist_ok=True)
PORT            = int(os.environ.get("PORT", 8585))

# ==================== LOGO URL ====================
LOGO_URL = "https://i.ibb.co.com/svHY0rms/icon.png"
# ⬆️ উপরের URL এর জায়গায় তোমার MAHEN লোগোর আসল লিংক বসাও

FIREBASE_HDRS = {
    "Content-Type": "application/json",
    "X-Android-Package": "ai.onmusic.app", "X-Android-Cert": "21C43B18DB08FBBE59D247923BA5A8B4F6AA3C29",
    "Accept-Language": "en-US", "X-Client-Version": "Android/Fallback/X23002001/FirebaseCore-Android",
    "X-Firebase-GMPID": "1:162323175591:android:e390852c016caa478be382",
    "X-Firebase-Client": "H4sIAAAAAAAAAKtWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Pixel Build/NHG47O)",
    "Accept-Encoding": "gzip",
}

# log -----------------------------------------------------------------
W="\033[97m"; G="\033[92m"; Y="\033[93m"; R="\033[91m"; C="\033[96m"; B="\033[1m"; X="\033[0m"
LOGFILE = os.path.join(HERE, "studio.log")
_lf = open(LOGFILE, "a", buffering=1, encoding="utf-8")
def _write(line):
    try:
        _lf.write(line + "\n")
    except Exception:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass
def log(tag, msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    _write(f"{C}[{t}]{X} {tag} {msg}")
def brk(title):
    _write(f"\n{'─'*18} {B}{title}{X} {'─'*18}\n")
def log_plain(msg):
    _write(msg)

# state ---------------------------------------------------------------
app = Flask(__name__)
LOCK, OWNER, DONE, ERROR = threading.Lock(), {}, {}, {}
_ACTIVE = {"last_job": None}
_DL_GUARD  = {}
_DL_GUARD_LOCK = threading.Lock()

def _flight_lock(job):
    with _DL_GUARD_LOCK:
        if job not in _DL_GUARD:
            _DL_GUARD[job] = threading.Lock()
        return _DL_GUARD[job]

# --------------------------- accounts --------------------------------
FIRST = ["Arjun","Rahul","Priya","Aarav","Ananya","Vikram","Sneha","Rohan","Ishaan","Diya","Kabir","Anaya",
         "Aditya","Meera","Karan","Neha","Ravi","Pooja","Rehan","Simran","Nikhil","Sahil","Tanvi","Varun",
         "Kavya","Mohit","Riya","Abhishek","Sanya","Ishita","Yash","Tanya","Kunal","Dev","Pranav","Vivaan","Ira"]
LAST  = ["Sharma","Verma","Kumar","Singh","Gupta","Yadav","Patel","Mehta","Iyer","Nair","Rao","Bose","Das",
         "Bhat","Desai","Shah","Pandey","Mishra","Arora","Kapoor","Malhotra","Chauhan","Pillai","Menon","Sahu","Rana"]
DOMAIN= ["gmail.com","yahoo.com","outlook.com","hotmail.com","icloud.com","zoho.com","aol.com"]

def new_account():
    f, l = random.choice(FIRST).lower(), random.choice(LAST).lower()
    s = random.randrange(6)
    u = {0:f+"."+l,1:f+l+str(random.randint(2,999)),2:f+str(random.randint(100,9999)),
         3:f+"."+l+str(random.randint(10,999)),4:l[0]+f}.get(s, f[0]+l+str(random.randint(1000,99999)))
    email, password = u+"@"+random.choice(DOMAIN), "N"+str(random.randint(10**7,10**8-1))+"m#Ei"
    log("ACCOUNT", f"minting fresh account  {G}{email}{X}")
    r   = requests.post(FIREBASE_SIGNUP, headers=FIREBASE_HDRS, json={"email": email, "password": password, "clientType":"CLIENT_TYPE_ANDROID"}, timeout=40)
    if r.status_code >= 400:
        raise RuntimeError(f"signup http {r.status_code}: {r.text[:120]}")
    d   = r.json()
    if "idToken" not in d or not d.get("localId"):
        raise RuntimeError("signup no account")
    log("ACCOUNT", f"{G}OK{X} localId={C}{d['localId']}{X}  email={email}")
    return {"token": d["idToken"], "localId": d["localId"], "email": email, "password": password}

# --------------------------- api layer --------------------------------
def _hd(token):
    return {"user-agent":"Dart/3.12 (dart:io)","x-brand":"on-music-ai","authorization":"Bearer "+token,
            "x-client-platform":"mobile","accept-encoding":"identity"}

def _call(token, method, rel, payload=None, **q):
    url = API_BASE + rel + (("?"+urllib.parse.urlencode(q)) if q else "")
    h   = _hd(token)
    if payload is not None: h["Content-Type"] = "application/json"
    return requests.request(method, url, headers=h, json=payload, timeout=90)

def submit_song(token, prompt, dur, vocals):
    body = {"tier":"pro","prompt":prompt,"durationSeconds":dur,"idempotencyKey":str(uuid.uuid4()),
            "displayContext":{"vocalsEnabled":vocals,"activeTab":"prompt","sourcePrompt":prompt}}
    r = _call(token,"POST","/music/generate",body)
    log("API", f"POST /music/generate -> {Y}{r.status_code}{X} {r.text[:90]}")
    if r.status_code not in (200,202):
        raise RuntimeError(f"generate {r.status_code}: {r.text[:140]}")
    return r.json()

def probe(token, job):
    r = _call(token,"GET","/music/jobs/"+job)
    if r.status_code >= 400:
        log("API", f"GET jobs/{job[:8]}… -> {R}{r.status_code}{X}")
        return None
    return r.json()

def _await_one(job, token):
    for i in range(400):
        try:
            d = probe(token, job)
        except Exception as e:
            log("WATCH", f"[{job[:8]}…] probe {R}ERR{X} {e}")
            d = None
        if not d:
            time.sleep(4); continue
        st = d.get("status")
        log("JOB", f"[{job[:8]}…] poll#{i:>3}  status={st}{'   (queue)' if st in ('PENDING','QUEUED') else ''}")
        if st == "COMPLETED":
            return {"ok": True, "status": st, "data": d}
        TERM = ("FAILED","ERROR","REJECTED","CANCELLED","FAILURE","REFUNDED","SUCCEEDED_NO_AUDIO","DELETED","EXPIRED")
        if st in TERM:
            reason = d.get("error") or d.get("message") or d.get("refundReason") or d.get("failureReason") or ""
            log("JOB", f"[{job[:8]}…] → {R}{st}{X}  reason={reason or 'n/a'}")
            return {"ok": False, "status": st, "reason": reason, "data": d}
        time.sleep(4)
    return {"ok": False, "status": "TIMEOUT", "reason": "poll timeout", "data": None}

REFUND_SAME_ACC_MAX = 2
_TOTAL_MAX_ATTEMPTS  = 6

def _produce(user_key, prompt, dur, vocals):
    acc = None
    attempt = 0
    refund_streak = 0
    last = "START"

    def register():
        if acc:
            with LOCK:
                OWNER[user_key] = {"token": acc["token"], "ttl": time.time() + 3600}

    def fresh():
        nonlocal acc, refund_streak
        acc = new_account()
        register()
        refund_streak = 0

    fresh()

    while attempt < _TOTAL_MAX_ATTEMPTS:
        attempt += 1
        try:
            job = submit_song(acc["token"], prompt, dur, vocals)
        except Exception as e:
            log("RETRY", f"attempt#{attempt} {R}submit failed{X}: {str(e)[:120]}")
            time.sleep(2)
            fresh(); continue
        rid = job.get("jobId")
        log("RETRY", f"[ticket {user_key[:8]}…] attempt#{attempt}/{_TOTAL_MAX_ATTEMPTS} → new job {Y}{rid}{X} (account {acc['email']})")
        res = _await_one(rid, acc["token"])
        if res["ok"]:
            d = res["data"]
            with LOCK:
                DONE[user_key] = d
                ERROR.pop(user_key, None)
                OWNER.pop(user_key, None)
            _save_meta(user_key, d)
            t0 = time.time()
            got = _download(user_key, d.get("audioUrl"))
            log("RETRY", f"[ticket {user_key[:8]}…] {B}{G}SUCCESS{X}  title={d.get('title')!r}  dur={d.get('durationSeconds')}s | mp3={'ready' if got else 'FAILED'} ({(time.time()-t0):.0f}s)")
            return
        st = res["status"]
        last = st
        reason = (res.get("reason") or "").strip()
        if st == "REFUNDED":
            refund_streak += 1
            log("RETRY", f"[ticket {user_key[:8]}…] {Y}REFUNDED{X} attempt#{attempt} → credits RETURNED, retrying same account ({refund_streak}/{REFUND_SAME_ACC_MAX})")
            if refund_streak >= REFUND_SAME_ACC_MAX:
                log("RETRY", f"[ticket {user_key[:8]}…] too many refunds on one account → minting a NEW account")
                fresh()
            else:
                register()
            time.sleep(2)
            continue
        log("RETRY", f"[ticket {user_key[:8]}…] {R}{st}{X} attempt#{attempt} → rotating to a NEW account (credit likely spent)")
        if reason:
            log("RETRY", f"         ↳ reason: {reason[:140]}")
        time.sleep(2)
        fresh()

    with LOCK:
        ERROR[user_key] = f"auto-retry exhausted after {_TOTAL_MAX_ATTEMPTS} attempts (last: {last})"
        log("RETRY", f"[ticket {user_key[:8]}…] {R}giving up{X} last={last}")

def _sfile(job):    return os.path.join(CACHE, re.sub(r"[^\w\-]", "", job or "")+".mp3")
def _mfile(job):   return os.path.join(CACHE, re.sub(r"[^\w\-]", "", job or "")+".meta.json")
def _save_meta(job, d):
    try:
        with open(_mfile(job), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception as e:
        log("META", f"sidecar write failed {e}")
def _load_meta(job):
    try:
        with open(_mfile(job), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
def _rescan_cache():
    n = 0
    with LOCK:
        for fn in os.listdir(CACHE):
            if fn.endswith(".meta.json") and _mp3_ready(fn[:-len(".meta.json")]):
                jid = fn[:-len(".meta.json")]
                m = _load_meta(jid)
                if m and jid not in DONE:
                    DONE[jid] = m
                    n += 1
    if n:
        log("META", f"restored {n} finished song(s) from disk cache")
def _mp3_ready(job):
    p = _sfile(job); return os.path.exists(p) and os.path.getsize(p) > 1000

def _download(job, url):
    if not url:
        log("MP3", f"[{job[:8]}…] no audioUrl yet — waiting"); return None
    out = _sfile(job)
    if _mp3_ready(job): return out
    lock = _flight_lock(job)
    if not lock.acquire(blocking=False):
        log("MP3", f"[{job[:8]}…] already downloading elsewhere — waiting")
        for _ in range(90):
            if _mp3_ready(job):
                return out
            time.sleep(2)
        return None
    tmp = out + ".part." + uuid.uuid4().hex[:8]
    try:
        log("MP3", f"[{job[:8]}…] downloading → cache")
        with requests.get(url, stream=True, timeout=(30, 600)) as r:
            if r.status_code != 200:
                log("MP3", f"[{job[:8]}…] http {R}{r.status_code}{X}")
                return None
            with open(tmp, "wb") as f:
                for c in r.iter_content(1 << 18):
                    if c: f.write(c)
            size = os.path.getsize(tmp)
            if size > 1000:
                if _mp3_ready(job):
                    try: os.remove(tmp)
                    except Exception: pass
                    return out
                os.replace(tmp, out)
                return out
        return None
    except Exception as e:
        log("MP3", f"[{job[:8]}…] {R}download error{X} {e}")
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except Exception: pass
        return None
    finally:
        try:
            lock.release()
        except Exception:
            pass

def _drop_leftovers(out):
    base = os.path.basename(out)
    try:
        for fn in os.listdir(CACHE):
            if fn.startswith(base) and not fn.endswith(".mp3"):
                os.remove(os.path.join(CACHE, fn))
    except Exception:
        pass

def _ensure(job):
    if _mp3_ready(job): return _sfile(job)
    d  = DONE.get(job) or _load_meta(job) or {}
    ow = OWNER.get(job)
    if d and d.get("audioUrl"): return _download(job, d["audioUrl"])
    if ow and ow["ttl"] > time.time():
        info = probe(ow["token"], job)
        if info and info.get("audioUrl"):
            with LOCK: DONE[job] = info; _save_meta(job, info)
            return _download(job, info["audioUrl"])
    if d.get("audioUrl") is None and d.get("status") == "COMPLETED":
        return None
    return None

# ----------------------------- SVG art -------------------------------
def _svg(title):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" '
            'viewBox="0 0 800 800"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#00d4ff"/><stop offset="1" stop-color="#7c3aed"/>'
            '</linearGradient></defs><rect width="800" height="800" fill="#0a0a12"/>'
            '<circle cx="620" cy="150" r="330" fill="#00d4ff" opacity=".15"/>'
            '<circle cx="140" cy="600" r="260" fill="#7c3aed" opacity=".2"/>'
            '<text x="400" y="440" font-size="260" text-anchor="middle" fill="url(#g)">\u266c</text>'
            '<text x="400" y="620" text-anchor="middle" font-family="Segoe UI,sans-serif" fill="url(#g)" '
            'font-weight="700" letter-spacing="6" font-size="44">'+title+'</text></svg>')

# ----------------------------- endpoints ------------------------------
@app.get("/api/health")
def health(): return jsonify(ok=True)

@app.get("/api/lib")
def api_lib():
    seen=set()
    out=[]
    if os.path.isdir(CACHE):
        for fn in os.listdir(CACHE):
            if fn.endswith(".meta.json"):
                jid=fn[:-len(".meta.json")]
                if _mp3_ready(jid):
                    m=_load_meta(jid) or {}
                    out.append({"id":jid,"title":m.get("title") or "Untitled",
                                "prompt":m.get("prompt") or "","dur":m.get("durationSeconds") or 0,
                                "model":m.get("modelId") or "","at":m.get("createdAt") or ""})
                    seen.add(jid)
    with LOCK:
        for job in list(DONE):
            if _mp3_ready(job) and job not in seen:
                d=DONE[job]
                _save_meta(job,d)
                out.append({"id":job,"title":d.get("title") or "Untitled","prompt":d.get("prompt") or "",
                            "dur":d.get("durationSeconds") or 0,"model":d.get("modelId") or "",
                            "at":d.get("createdAt") or ""})
    out.sort(key=lambda s:s.get("at") or "", reverse=True)
    return jsonify(songs=out)

@app.post("/api/generate")
def api_generate():
    data  = request.get_json(silent=True) or {}
    prompt= re.sub(r"\s+"," ",(data.get("prompt") or "")).strip()
    if len(prompt) < 2: return jsonify(error="write a prompt"), 400
    dur   = int(data.get("durationSeconds") or 120)
    if dur not in (30,60,120): dur=120
    vocals= bool(data.get("vocals", True))
    brk(f" NEW GENERATION TICKET ")
    log("REQ", f"prompt  = {W}{prompt}{X}")
    log("REQ", f"dur     = {dur}s   vocals={vocals}")
    ticket = str(uuid.uuid4())
    with LOCK:
        _ACTIVE["last_job"] = ticket
    log("JOB", f"ticket  = {B}{Y}{ticket}{X}  (auto-retry engine will drive it)")
    threading.Thread(target=_produce, args=(ticket, prompt, dur, vocals), daemon=True).start()
    return jsonify(jobId=ticket, model="lyria-3-pro", autoRetry=True)


@app.get("/api/status/<job>")
def api_status(job):
    if _mp3_ready(job):
        d = DONE.get(job) or _load_meta(job) or {}
        log("UI", f"polled status [{job[:8]}…] → {G}done{X} mp3 ready")
        return jsonify(status="done", mp3Ready=True,
                       title=(d.get('title') or 'Untitled'), dur=d.get('durationSeconds') or 0)
    with LOCK:
        if job in ERROR:          return jsonify(status="error", error=ERROR[job])
        if job in DONE:
            log("UI",  f"polled status [{job[:8]}…] → {G}done{X} mp3={'y' if _mp3_ready(job) else 'downloading'}")
            return jsonify(status="done", mp3Ready=_mp3_ready(job),
                           title=(DONE[job].get('title') or 'Untitled'),
                           dur=DONE[job].get('durationSeconds') or 0)
        if job in OWNER:
            log("UI", f"polled status [{job[:8]}…] → {Y}watcher still running{X}")
    return jsonify(status="working")

@app.get("/api/meta/<job>")
def api_meta(job):
    m = _load_meta(job)
    if not m: m = DONE.get(job)
    if not m: return jsonify({}), 404
    return jsonify({"id":job,"title":m.get("title") or "Untitled","prompt":m.get("prompt") or "",
                    "lyrics":m.get("lyrics") or "","dur":m.get("durationSeconds") or 0,"model":m.get("modelId") or ""})

def _ensure_mp3_quick(job):
    if _mp3_ready(job): return _sfile(job)
    return None

@app.get("/api/audio/<job>")
def api_audio(job):
    mp = _ensure(job)
    if mp:
        return send_from_directory(CACHE, os.path.basename(mp), mimetype="audio/mpeg", conditional=True)
    return jsonify(error="not ready yet"), 404

@app.get("/api/download/<job>")
def api_download(job):
    for _ in range(90):
        mp=_ensure(job)
        if mp: break
        time.sleep(4)
    else:
        mp=_sfile(job)
    if not os.path.exists(mp) or os.path.getsize(mp) < 1000:
        return jsonify(error="still preparing"), 202
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    fname = "song-" + today + ".mp3"
    log("DL", f"sending mp3 [{job[:8]}…] as '{fname}'")
    resp = send_from_directory(CACHE, os.path.basename(mp), as_attachment=True,
                               download_name=fname, mimetype='audio/mpeg')
    return resp

@app.get("/api/cover/<job>")
def api_cover(job):
    if not re.fullmatch(r"[A-Za-z0-9\-]+", job or ""):
        return Response(_svg("MAHEN"), content_type="image/svg+xml")
    try:
        r = requests.get(COVER_BASE.format(job=job), timeout=9)
        if r.status_code == 200 and r.content and r.headers.get('content-type', '').startswith('image'):
            return Response(r.content, content_type=r.headers['content-type'], headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        pass
    return Response(_svg("MAHEN"), content_type="image/svg+xml")

@app.delete("/api/song/<job>")
def api_delete_song(job):
    if not re.fullmatch(r"[A-Za-z0-9\-]+", job or ""):
        return jsonify(ok=False), 400
    removed = {"mp3": False, "meta": False}
    mp, meta = _sfile(job), _mfile(job)
    try:
        if os.path.exists(mp):
            os.remove(mp); removed["mp3"] = True
    except Exception as e:
        log("DEL", f"mp3 remove failed {e}")
    try:
        if os.path.exists(meta):
            os.remove(meta); removed["meta"] = True
    except Exception as e:
        log("DEL", f"meta remove failed {e}")
    with LOCK:
        DONE.pop(job, None); ERROR.pop(job, None); OWNER.pop(job, None)
    log("DEL", f"deleted song [{job[:8]}…]  mp3={removed['mp3']} meta={removed['meta']}")
    return jsonify(ok=removed["mp3"] or removed["meta"])

INDEX = None

# =====================================================================
#   MAHEN MUSE — NEW UI (Splash + Logo + Credit)
# =====================================================================
_UI = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#0a0a12">
<title>MAHEN Muse</title>
<style>
:root{
  --bg:#0a0a12; --panel:#14121e; --ink:#f0edff; --mut:#8b85a3; --line:#252036;
  --red:#00d4ff; --red2:#7c3aed; --grad:linear-gradient(115deg,#00d4ff,#7c3aed);
  --darkred:#0099cc; --sh:0 8px 30px rgba(0,212,255,.08);
  --soft:#1a1728; --tgl:#2a2540;
  --r:22px; --ios:env(safe-area-inset-bottom)
}
body.light{
  --bg:#f7f7f8; --panel:#ffffff; --ink:#1c1c1e; --mut:#71717a; --line:#ececef;
  --red:#00b8e6; --red2:#7c3aed; --grad:linear-gradient(115deg,#00b8e6,#7c3aed);
  --darkred:#0099cc; --sh:0 8px 30px rgba(0,0,0,.05);
  --soft:#f2f2f5; --tgl:#e4e4e9
}
*{-webkit-box-sizing:border-box;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--ink);height:100%;
 font-family:-apple-system,'SF Pro Text',Segoe UI,Roboto,'Helvetica Neue',sans-serif;-webkit-font-smoothing:antialiased;
 overflow-x:hidden}
.app{max-width:540px;margin:0 auto;padding:14px 16px calc(150px + var(--ios));display:block}

/* ==================== SPLASH SCREEN ==================== */
#splash{
  position:fixed;inset:0;z-index:9999;background:linear-gradient(135deg,#0a0a12,#14121e,#1a0a2e);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  transition:opacity .6s ease,visibility .6s ease;
}
#splash.hide{opacity:0;visibility:hidden;pointer-events:none}
#splash .logo-wrap{
  position:relative;width:180px;height:180px;
  animation:splashPulse 2s ease-in-out infinite;
}
#splash .logo-wrap img{
  width:100%;height:100%;object-fit:cover;border-radius:50%;
  box-shadow:0 0 60px rgba(0,212,255,.5),0 0 120px rgba(124,58,237,.3);
  border:3px solid rgba(0,212,255,.3);
}
#splash .logo-wrap::before{
  content:'';position:absolute;inset:-15px;border-radius:50%;
  border:2px solid transparent;border-top-color:#00d4ff;border-right-color:#7c3aed;
  animation:spin 1.5s linear infinite;
}
#splash .logo-wrap::after{
  content:'';position:absolute;inset:-25px;border-radius:50%;
  border:2px solid transparent;border-bottom-color:#00d4ff;border-left-color:#7c3aed;
  animation:spin 2s linear infinite reverse;
}
#splash .brand{
  margin-top:32px;font-size:28px;font-weight:900;letter-spacing:4px;
  background:linear-gradient(115deg,#00d4ff,#7c3aed,#00d4ff);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
  background-size:200% auto;animation:shine 3s linear infinite;
  text-shadow:0 0 30px rgba(0,212,255,.3);
}
#splash .tagline{
  margin-top:8px;font-size:12px;color:#8b85a3;letter-spacing:2px;
  text-transform:uppercase;font-weight:700;
  animation:fadeUp .8s ease .3s both;
}
#splash .loadbar{
  margin-top:40px;width:180px;height:3px;background:rgba(255,255,255,.1);
  border-radius:99px;overflow:hidden;
}
#splash .loadbar .fill{
  height:100%;width:0;background:linear-gradient(90deg,#00d4ff,#7c3aed);
  border-radius:99px;animation:loadFill 2s ease-in-out forwards;
}
#splash .dots{
  margin-top:20px;display:flex;gap:8px;
}
#splash .dots span{
  width:8px;height:8px;border-radius:50%;background:#00d4ff;
  animation:dotPulse 1.4s ease-in-out infinite;
}
#splash .dots span:nth-child(2){animation-delay:.2s;background:#7c3aed}
#splash .dots span:nth-child(3){animation-delay:.4s;background:#00d4ff}

@keyframes splashPulse{
  0%,100%{transform:scale(1);filter:brightness(1)}
  50%{transform:scale(1.05);filter:brightness(1.2)}
}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes shine{to{background-position:200% center}}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes loadFill{0%{width:0}100%{width:100%}}
@keyframes dotPulse{
  0%,100%{transform:scale(1);opacity:.4}
  50%{transform:scale(1.4);opacity:1}
}

/* ==================== MAIN APP ==================== */
.float{position:fixed;inset:0;z-index:-1;background:
  radial-gradient(120% 80% at 0% 0%,#14121e 0%,#0a0a12 60%,#080810 100%)}
body.light .float{background:
  radial-gradient(120% 80% at 0% 0%,#ffffff 0%,#f7f7f8 60%,#f0f0f5 100%)}

/* header */
.top{display:flex;align-items:center;gap:11px;padding:4px 2px 16px}
.mark{width:42px;height:42px;border-radius:12px;overflow:hidden;flex:0 0 auto;
 box-shadow:0 6px 22px rgba(0,212,255,.4);border:2px solid rgba(0,212,255,.4)}
.mark img{width:100%;height:100%;object-fit:cover;display:block}
.big{font-size:19px;font-weight:800;letter-spacing:-.3px;line-height:1}
.big small{display:block;font-size:10.5px;font-weight:700;background:var(--grad);
 -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
 letter-spacing:.4px;text-transform:uppercase;margin-top:3px}
.pull{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:800;
 color:#00d4ff;background:rgba(0,212,255,.1);border:1px solid rgba(0,212,255,.3);
 padding:5px 10px;border-radius:99px}
body.light .pull{color:#00b8e6;background:rgba(0,184,230,.1);border-color:rgba(0,184,230,.3)}
.buttonspace{display:flex;align-items:center;gap:8px;margin-left:auto}
.themebtn{width:38px;height:38px;border-radius:12px;border:1px solid var(--line);background:var(--panel);
 color:var(--ink);cursor:pointer;display:grid;place-items:center;font-size:17px;flex:0 0 auto;transition:.15s;
 box-shadow:0 3px 10px rgba(0,0,0,.15)}
.themebtn:active{transform:scale(.9)}

h1.hd{font-size:26px;letter-spacing:-.5px;line-height:1.15;font-weight:800;margin:6px 0 4px}
h1.hd b{background:var(--grad);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.sub{color:var(--mut);font-size:13.5px;line-height:1.5;margin:0 0 16px}

.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:16px;
 box-shadow:var(--sh);margin-bottom:14px}
.hlab{font-size:11px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:var(--mut);margin-bottom:10px}
.hlab em{font-style:normal;margin-right:6px}
.pills{display:flex;gap:8px;overflow-x:auto;padding-bottom:3px;scrollbar-width:none}
.pills::-webkit-scrollbar{display:none}
.pil{flex:0 0 auto;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:99px;
 padding:8px 14px;font-size:12.5px;font-weight:700;cursor:pointer;transition:.12s;user-select:none}
.pil.on{background:var(--grad);border-color:transparent;color:#fff;box-shadow:0 6px 16px rgba(0,212,255,.3)}
textarea{width:100%;background:var(--soft);border:1px solid var(--line);border-radius:14px;color:var(--ink);
 padding:13px;min-height:96px;resize:vertical;font-family:inherit;font-size:15px;line-height:1.5;outline:none;transition:.15s;
 caret-color:var(--red)}
textarea::placeholder{color:var(--mut)}
textarea:focus{border-color:var(--red);box-shadow:0 0 0 3px rgba(0,212,255,.15);background:var(--panel)}
.tools{display:flex;align-items:center;gap:14px;margin-top:13px;flex-wrap:wrap}
.tgl{display:flex;align-items:center;gap:7px;font-size:12.5px;color:var(--mut);font-weight:700;cursor:pointer}
.tgl input{display:none}
.tgl .k{width:42px;height:24px;border-radius:99px;background:var(--tgl);position:relative;transition:.18s}
.tgl .k::after{content:'';position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;
 box-shadow:0 1px 4px rgba(0,0,0,.25);transition:.18s}
.tgl input:checked+.k{background:var(--red)}
.tgl input:checked+.k::after{transform:translateX(18px)}
.durbox{display:inline-flex;background:var(--soft);border-radius:99px;padding:3px;gap:2px}
.durbox button{border:0;background:transparent;color:var(--mut);font-size:12px;font-weight:800;padding:7px 12px;border-radius:99px;cursor:pointer}
.durbox button.on{background:var(--panel);color:var(--red);box-shadow:0 1px 5px rgba(0,0,0,.14)}
.gorow{margin-top:15px}
.go{width:100%;border:0;cursor:pointer;background:var(--grad);color:#fff;border-radius:14px;height:52px;
 font-size:15px;font-weight:800;display:flex;align-items:center;justify-content:center;gap:9px;
 box-shadow:0 10px 24px rgba(0,212,255,.35);transition:.12s}
.go:active{transform:scale(.98)}
.go:disabled{opacity:.5;cursor:not-allowed}
.go .rr{display:none;width:16px;height:16px;border:2px solid #fff6;border-top-color:#fff;border-radius:50%;
 animation:sp 0.7s linear infinite}
.go.load{pointer-events:none}.go.load .rr{display:block}
@keyframes sp{to{transform:rotate(1turn)}}

/* progress */
.ph{display:flex;align-items:center;gap:14px}
.ph .ic{width:44px;height:44px;flex:0 0 auto;border-radius:13px;background:rgba(0,212,255,.12);color:#00d4ff;
 display:grid;place-items:center;font-size:21px}
.ph b{display:block;font-size:15px}.ph .stt{color:var(--mut);font-size:12.5px;margin-top:3px}
.qb{margin-top:6px;height:6px;border-radius:99px;background:rgba(0,212,255,.15);overflow:hidden}
.qf{height:100%;width:0;background:var(--grad);border-radius:99px;transition:.4s}
.ticks{display:flex;align-items:center;gap:4px;justify-content:center;height:40px;margin-top:8px}
.tk1{width:6px;height:10px;border-radius:6px;background:#00d4ff;opacity:.35;animation:eq 1s ease-in-out infinite}
@keyframes eq{0%,100%{height:9px;opacity:.35}50%{height:38px;opacity:.8}}

/* player */
.ply{text-align:center}
.cov{margin:2px auto 18px;position:relative;display:inline-block}
.cov img{width:min(60vw,250px);aspect-ratio:1;object-fit:cover;border-radius:18px;
 box-shadow:0 20px 44px rgba(0,212,255,.2);background:var(--soft)}
.pname{font-size:19px;font-weight:800;letter-spacing:-.2px;margin:0}
.pmeta{color:var(--mut);font-size:12px;font-weight:700;margin-top:7px}
.slider{width:100%;margin-top:20px;-webkit-appearance:none;appearance:none;height:6px;border-radius:99px;
 background:var(--soft);outline:none}
.slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:18px;height:18px;border-radius:50%;
 background:#fff;border:3px solid var(--red);box-shadow:0 2px 8px rgba(0,212,255,.4)}
.times{display:flex;justify-content:space-between;font-size:11px;color:var(--mut);font-weight:700;margin-top:5px;font-variant-numeric:tabular-nums}
.pbtn{display:flex;align-items:center;justify-content:center;gap:26px;margin-top:8px}
.circ{border:0;cursor:pointer;width:52px;height:52px;border-radius:50%;display:grid;place-items:center;
 background:var(--panel);color:var(--red);box-shadow:0 6px 18px rgba(0,0,0,.08);transition:.12s}
.circ:hover{background:var(--soft)}
.bigbtn{width:64px;height:64px;background:var(--grad);color:#fff;box-shadow:0 10px 24px rgba(0,212,255,.4)}
.acts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:20px}
.abtn{height:50px;border-radius:13px;cursor:pointer;font-size:14px;font-weight:800;display:flex;
 align-items:center;justify-content:center;gap:8px;transition:.12s}
.abtn.pr{background:var(--grad);color:#fff;border:0;box-shadow:0 8px 20px rgba(0,212,255,.3)}
.abtn.gh{border:1px solid var(--line);background:var(--panel);color:var(--ink)}
.lyr{margin-top:18px;text-align:left;border-top:1px solid var(--line);padding-top:14px}
.lyr h5{margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--mut)}
.lyr pre{margin:0;white-space:pre-wrap;font-size:13.5px;line-height:1.8;color:var(--ink);max-height:300px;overflow:auto}

/* library */
.lhead{display:flex;align-items:center;gap:10px;margin:6px 0 4px}
.lhead h2{margin:0;font-size:19px;font-weight:800}
.lhead .n{margin-left:auto;color:var(--mut);font-size:12px;font-weight:700}
.gcard{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-top:6px}
.lc{background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden;cursor:pointer;transition:.1s;position:relative}
.lc:hover{box-shadow:0 8px 24px rgba(0,212,255,.1)}
.lc img{width:100%;aspect-ratio:1;object-fit:cover;background:var(--soft);display:block}
.lc .in{padding:9px 11px 12px}
.lc .tt{font-size:12.5px;font-weight:800;margin:0;-webkit-line-clamp:2;display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden}
.lc .pw{font-size:11px;color:var(--mut);margin-top:3px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.lc .tm{display:inline-block;margin-top:7px;font-size:10px;font-weight:800;color:var(--red);
 background:rgba(0,212,255,.12);padding:2px 8px;border-radius:99px}
.deltoday{position:absolute;top:8px;right:8px;z-index:3;width:30px;height:30px;border-radius:10px;
 border:0;cursor:pointer;font-size:14px;line-height:1;display:grid;place-items:center;
 background:rgba(20,18,30,.92);color:#00d4ff;box-shadow:0 2px 8px rgba(0,0,0,.4);transition:.12s;
 -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
.deltoday:active{transform:scale(.88)}
body.light .deltoday{background:rgba(255,255,255,.92);color:#00b8e6}
.lc .imghost{position:relative}
.lc .artph{width:100%;aspect-ratio:1;background:linear-gradient(135deg,rgba(0,212,255,.15),rgba(124,58,237,.15));
 display:grid;place-items:center;font-size:56px;color:#00d4ff}

/* nav */
.dockm{position:fixed;left:50%;bottom:calc(10px + var(--ios));transform:translateX(-50%);
 width:min(86vw,400px);background:rgba(20,18,30,.92);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px);
 border:1px solid var(--line);border-radius:24px;display:flex;padding:5px;box-shadow:0 -6px 30px rgba(0,0,0,.3)}
body.light .dockm{background:rgba(255,255,255,.92);box-shadow:0 -6px 30px rgba(0,0,0,.06)}
.dockm button{flex:1;border:0;background:transparent;height:46px;border-radius:19px;color:var(--mut);cursor:pointer;
 display:flex;align-items:center;justify-content:center;gap:6px;font-size:13px;font-weight:800}
.dockm button svg{width:18px;height:18px;fill:currentColor}
.dockm button.on{background:var(--panel);color:var(--red);box-shadow:0 3px 12px rgba(0,212,255,.2)}
.empt{text-align:center;color:var(--mut);padding:52px 10px}
.empt b{display:block;font-size:44px;margin-bottom:8px;opacity:.5}
@keyframes pop{from{opacity:0;transform:scale(.96)}to{opacity:1}}
.pop{animation:pop .3s}
.msg{position:fixed;left:50%;bottom:calc(86px + var(--ios));transform:translateX(-50%);
 background:#222;color:#fff;padding:10px 18px;border-radius:12px;font-size:12.5px;font-weight:700;z-index:40;
 display:none;box-shadow:0 8px 24px rgba(0,0,0,.2)}
.view{display:none}.view.on{display:block;animation:pop .25s}
.againbp{background:none;border:0;color:var(--red);font:inherit;font-size:13px;cursor:pointer;margin-top:16px;font-weight:700}
.toastr{position:fixed;left:0;right:0;bottom:calc(90px + var(--ios));z-index:50;display:flex;flex-direction:column;
 align-items:center;gap:8px;pointer-events:none}
.toastx{background:#14121e;color:#fff;padding:10px 16px;border-radius:12px;font-size:12.5px;font-weight:700;
 display:flex;gap:8px;align-items:center;box-shadow:0 10px 30px rgba(0,0,0,.35);animation:pop .2s;max-width:88vw;
 border:1px solid rgba(0,212,255,.2)}
.toastx.ok i{color:#00d4ff}.toastx.bad i{color:#ff5b70}.toastx i{font-style:normal;font-weight:900}

/* footer credit */
.credit{
  text-align:center;padding:20px 10px 8px;font-size:11.5px;color:var(--mut);
  letter-spacing:.5px;font-weight:700;
}
.credit b{
  background:var(--grad);-webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;font-weight:900;letter-spacing:1px;
}
</style>
</head><body>

<!-- ==================== SPLASH SCREEN ==================== -->
<div id="splash">
  <div class="logo-wrap">
    <img src="__LOGO_URL__" alt="MAHEN" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 200%22><defs><linearGradient id=%22g%22 x1=%220%22 y1=%220%22 x2=%221%22 y2=%221%22><stop offset=%220%22 stop-color=%22%2300d4ff%22/><stop offset=%221%22 stop-color=%22%237c3aed%22/></linearGradient></defs><rect width=%22200%22 height=%22200%22 fill=%22%230a0a12%22/><circle cx=%22100%22 cy=%22100%22 r=%2270%22 fill=%22url(%23g)%22 opacity=%220.3%22/><text x=%22100%22 y=%22130%22 font-size=%2280%22 font-weight=%22bold%22 text-anchor=%22middle%22 fill=%22url(%23g)%22 font-family=%22Arial%22>M</text></svg>'">
  </div>
  <div class="brand">MAHEN</div>
  <div class="tagline">AI Song Maker</div>
  <div class="loadbar"><div class="fill"></div></div>
  <div class="dots"><span></span><span></span><span></span></div>
</div>

<div class="float"></div>
<div class="app">

  <div class="top">
    <div class="mark">
      <img src="__LOGO_URL__" alt="MAHEN" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 200%22><defs><linearGradient id=%22g%22 x1=%220%22 y1=%220%22 x2=%221%22 y2=%221%22><stop offset=%220%22 stop-color=%22%2300d4ff%22/><stop offset=%221%22 stop-color=%22%237c3aed%22/></linearGradient></defs><rect width=%22200%22 height=%22200%22 fill=%22%230a0a12%22/><text x=%22100%22 y=%22130%22 font-size=%2280%22 font-weight=%22bold%22 text-anchor=%22middle%22 fill=%22url(%23g)%22 font-family=%22Arial%22>M</text></svg>'">
    </div>
    <div style="line-height:1">
      <div class="big">MAHEN <small>AI Song MAKER</small></div>
    </div>
    <div class="buttonspace">
      <div class="pull"><span>●</span> LIVE</div>
      <button class="themebtn" id="themeT" title="Toggle dark / light">☀️</button>
    </div>
  </div>

 <div class="view on" id="v-main">
   <div class="card">
     <div class="hlab"><em>🎚️</em>Mood</div>
     <div class="pills" id="moods"></div>
   </div>
   <div class="card">
     <div class="hlab"><em>✍️</em>Describe</div>
     <textarea id="pt" maxlength="500" placeholder="আপনার গানটি লিরিক্স লিখে দিন"></textarea>
     <div class="tools">
       <label class="tgl"><input type="checkbox" id="voc" checked><span class="k"></span>Vocals</label>
       <div class="durbox"><button data-d="30">0:30</button><button data-d="60">1:00</button><button data-d="120" class="on">2:00</button></div>
     </div>
     <div class="gorow"><button class="go" id="cgo"><span class="rr"></span><span id="goTxt">Compose Song</span></button></div>
   </div>

   <div class="card pop" id="prog" style="display:none">
     <div class="ph">
        <div class="ic" id="pico">🎼</div>
        <div style="flex:1"><b id="ptit">Working…</b><div class="stt" id="ptsub">‎</div></div>
     </div>
     <div style="height:12px"></div>
     <div class="qb"><div class="qf" id="qbar"></div></div>
     <div class="ticks" id="eqt"></div>
   </div>

   <div class="card pop ply" id="player" style="display:none"></div>
   <div class="card pop" id="lyrpan" style="display:none"></div>
 </div>

 <div class="view" id="v-lib">
   <div class="lhead"><h2>Library</h2><span class="n" id="lcount"></span></div>
   <div class="gcard" id="lgrid"></div>
 </div>

 <div class="credit">Developed by <b>MAHEN</b></div>
</div>

<nav class="dockm">
  <button class="on" data-v="v-main"><svg viewBox="0 0 24 24"><path d="M12 3l9 8h-3v9h-5v-6h-2v6H6v-9H3z"/></svg>MAKER</button>
  <button data-v="v-lib"><svg viewBox="0 0 24 24"><path d="M6 3h12a2 2 0 0 1 2 2v3H4V5a2 2 0 0 1 2-2zm-2 7h16v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-9z"/></svg>Library</button>
</nav>

<div class="toastr" id="tr"></div>
<div class="msg" id="mm">‎</div>
<audio id="aud" style="display:none"></audio>

<script>
"use strict";
const $=x=>document.getElementById(x), $$=x=>Array.from(document.querySelectorAll(x));
const esc=s=>{const e=document.createElement('span');e.textContent=s==null?'':String(s);return e.innerHTML};
let cur={
  busy:false, mood:0, dur:120, voc:true, job:null, meta:null, playing:false, ch:null, tim:null
};

/* ---- SPLASH SCREEN ---- */
window.addEventListener('load', () => {
  setTimeout(() => {
    const s = document.getElementById('splash');
    if (s) s.classList.add('hide');
  }, 2400);
});

/* ---- dark / light theme ---- */
function applyTheme(light){
  document.body.classList.toggle('light', light);
  const b=$('themeT');
  if(b) b.textContent = light ? '🌙' : '☀️';
  metaTheme(light);
}
function metaTheme(l){ const m=document.querySelector('meta[name="theme-color"]'); if(m) m.setAttribute('content', l?'#f7f7f8':'#0a0a12'); }
(function(){
  let light;
  try{ light = JSON.parse(localStorage.getItem('MAHEN_theme')||'null'); }
  catch(e){ light=null; }
  if(light===null){ light = true; }
  applyTheme(!!light);
  const b=$('themeT');
  if(b) b.addEventListener('click', ()=>{
    const nl = !document.body.classList.contains('light');
    try{ localStorage.setItem('MAHEN_theme', JSON.stringify(nl)); }catch(e){}
    applyTheme(nl);
  });
})();

const MOOD=[['Everything','whatever mood feels right, expressive and tasteful'],
 ['Desi Rap','upbeat desi punjabi rap with punchy 808s and punch flow'],
 ['Bollywood','emotional bollywood song with strings and dramatic build'],
 ['Synthwave','neon synthwave retrowave, driving analog bass'],
 ['Lo-fi','chill lo-fi beat, dusty vinyl and mellow keys'],
 ['Acoustic','warm raw acoustic folk with honest vocal'],
 ['R&B','smooth sultry R&B with velvet vocal runs'],
 ['EDM','uplifting festival EDM with euphoric drops'],
 ['Trap','dark aggressive trap with rolling 808s'],
 ['Ballad','slow heartfelt piano ballad']];
(function(){const h=$('moods');MOOD.forEach((m,i)=>{const b=document.createElement('span');b.className='pil'+(i?'':' on');b.textContent=m[0];b.onclick=()=>{$$('#moods .pil').forEach(p=>p.classList.remove('on'));b.classList.add('on');cur.mood=i;};h.appendChild(b);});})();
$$('.durbox button').forEach(b=>b.onclick=()=>{$$('.durbox button').forEach(x=>x.classList.remove('on'));b.classList.add('on');cur.dur=+b.dataset.d;});
$('voc').addEventListener('change',e=>cur.voc=e.target.checked);
$$('.dockm button').forEach(b=>b.onclick=()=>{show(b.dataset.v);});
function show(id){$$('.view').forEach(v=>v.classList.toggle('on',v.id===id));$$('.dockm button').forEach(x=>x.classList.toggle('on',x.dataset.v===id));if(id==='v-lib')lib();}
function tx(m,ok){const t=document.createElement('div');t.className='toastx '+(ok?'ok':'bad');t.innerHTML=`<i>${ok?'✓':'!'}</i><span>${esc(m)}</span>`;$('tr').appendChild(t);setTimeout(()=>{t.style.transition='opacity .4s';t.style.opacity='0';setTimeout(()=>t.remove(),450);},2400);}
function eq(){const host=$('eqt');host.innerHTML='';for(let i=0;i<12;i++){const s=document.createElement('div');s.className='tk1';s.style.animationDelay=(i*.09)+'s';s.style.animationIterationCount='infinite';host.appendChild(s);}}

async function gen(){
 if(cur.busy)return;
 const typed=$('pt').value.trim();
 let full;
 if(typed){ full=(cur.mood?MOOD[cur.mood][0]+' : ':'')+typed; }
 else{ full= cur.mood? MOOD[cur.mood][1] : 'expressive cinematic song, tasteful and warm'; }
 if(full.length<3){tx('Write what you want (or pick a mood) ✍️',false);return;}
 cur.busy=true;
 const g=$('cgo');
 g.classList.add('load'); $('goTxt').textContent='Generating…';
 $('qbar').style.width='6%';
 $('prog').style.display='block';$('player').style.display='none';$('lyrpan').style.display='none';
 setPh('⚙️','Minting fresh account…','fresh trial = 20 credits = 1 song');
 let R,j;
 try{ R=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:full,vocals:cur.voc,durationSeconds:cur.dur})});
      j=await R.json(); }catch(e){}
 if(!R||!R.ok||!j.jobId){ resetGen(g); tx((j&&j.error)||'start failed',false); return; }
 cur.job=j.jobId; $('qbar').style.width='24%';
 setPh('🎵','AI composing…','usually takes 1–3 min');
 try{ await tick(cur.job); }
 catch(e){ resetGen(g); $('prog').style.display='none'; tx(e.message||'generation failed',false); }
}
function resetGen(g){ cur.busy=false; if(g){g.classList.remove('load');$('goTxt').textContent='Compose Song';} }
$('cgo').addEventListener('click',gen);$('pt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();gen();}});

function setPh(i,t,s){$('pico').textContent=i;$('ptit').textContent=t;$('ptsub').textContent=s;}
async function tick(job){
 return new Promise((ok,no)=>{
   const poll=async()=>{
     try{
       const R=await fetch('/api/status/'+job);const d=await R.json();
       if(d.status==='done'){clearInterval(cur.tim); await finish(d); ok();}
       else if(d.status==='error'){clearInterval(cur.tim);no(new Error(d.error||'generation failed'));}
     }catch(e){}
   };
   poll(); cur.tim=setInterval(poll,2500);
 });
}
async function finish(d){
 $('qbar').style.width='96%';setPh('🎧','Finalizing audio…','waiting for the mastered MP3');
 let ready=d.mp3Ready===true, tries=0;
 while(!ready && tries<30){
   try{
     const s=await (await fetch('/api/status/'+cur.job)).json();
     if(s.mp3Ready===true){ ready=true; break; }
   }catch(e){}
   tries++;
   await new Promise(r=>setTimeout(r,2000));
 }
 const m=await (await fetch('/api/meta/'+cur.job)).json();
 $('qbar').style.width='100%';cur.meta=m;m.mp3=ready;
 setTimeout(()=>{$('prog').style.display='none';},400);
 show('v-main');
 if(ready){ drawPlayer(); } else {
   $('player').style.display='none';
   tx('MP3 still uploading — tap Download MP3 when it appears',false,3500);
 }
 $('lyrpan').style.display=m.lyrics?'block':'none';
 if(m.lyrics){$('lyrpan').innerHTML='<h5>Lyrics</h5><pre>'+esc(m.lyrics)+'</pre>';}
 resetGen($('cgo'));
 tx('Song ready!'+(ready?' Hit play 🙂':''));
}
function fmt(s){s=isFinite(s)?Math.max(0,Math.round(s)):0;return Math.floor(s/60)+':'+(s%60<10?'0':'')+s%60;}
 function drawPlayer(){
  const j=cur.job,m=cur.meta;
  const h=$('player');
  h.style.display='block';
  const dur=fmt(m.dur||0);
  h.innerHTML=`
  <div class="cov"><img src="/api/cover/${j}"></div>
  <div class="pname">${esc(m.title||'Your Song')}</div>
  <div class="pmeta">MAHEN Muse · lyria · MP3</div>
  <div style="margin-top:16px">
    <div class="times"><span id="ct">0:00</span><span>${dur}</span></div>
    <input id="seeks" class="slider" min="0" max="100" value="0" step="0.05">
  </div>
  <div class="pbtn">
    <button class="circ" id="bk">⏪</button>
    <button class="circ bigbtn" id="pp">▶</button>
    <button class="circ" id="fw">⏩</button>
  </div>
  <div class="acts">
    <button class="abtn pr" id="dl">⬇&nbsp; Download MP3</button>
  </div>
  <button class="againbp" id="ag">+ Compose another</button>`;
 wire(j,m.mp3);
 $('ag').onclick=()=>{$('pt').value='';$('pt').focus();};
}
function wire(j,mp3ready){
 const a=$('aud'),pp=$('pp'),seeks=$('seeks');
 const upd=()=>pp.textContent=(a.paused&&!cur.playing)?'▶':'❚❚';
 $('pp').onclick=()=>{a.paused?a.play():a.pause();};
 upd();
 $('bk').onclick=()=>a.currentTime-=15;$('fw').onclick=()=>a.currentTime=Math.min(a.duration||99999,a.currentTime+15);
 a.addEventListener('timeupdate',()=>{ if(!a.duration)return; const p=a.currentTime/a.duration*100;
   seeks.value=p; $('ct').textContent=fmt(a.currentTime); });
 seeks.addEventListener('input',()=>{ if(a.duration) a.currentTime=seeks.value/100*a.duration; });
 a.addEventListener('play',upd);a.addEventListener('pause',upd);
 $('dl').onclick=()=>{ tx('Downloading…'); const x=document.createElement('a');x.href='/api/download/'+j;x.click(); };
 a.src='/api/audio/'+j+'?v='+Date.now();
 let at=0;a.onerror=function(){ if(at++<8){setTimeout(()=>{a.src='/api/audio/'+j+'?v='+Date.now()+at;a.load();},2500*at);}else tx('still cooking — try download',false); };
 a.load();
}
async function lib(){
 const R=await fetch('/api/lib');const d=await R.json();const s=d.songs||[];
 $('lcount').textContent = s && s.length ? s.length+' song'+(s.length===1?'':'s') : '0 songs';
 renderLib(s);
}
function renderLib(s){
 const g=$('lgrid');g.innerHTML='';
 if(!s.length){
  g.innerHTML=`<div class="empt" style="grid-column:1/-1;min-height:46vh;display:flex;flex-direction:column;align-items:center;justify-content:center">
    <b>🎤</b><div style="font-weight:800;font-size:15px;color:var(--mut)">Library is empty</div>
    <div style="color:var(--mut);margin-top:4px">Go to MAKER and compose your first song</div></div>`;
  return;
 }
 s.forEach(x=>{
  const c=document.createElement('div');c.className='lc';c.dataset.id=x.id;
  c.innerHTML=`<div class="imghost"><img src="/api/cover/${x.id}" loading="lazy" onerror="this.outerHTML='<div class=artph>♪</div>'" alt="cover"></div>
   <button class="deltoday" title="Delete" aria-label="Delete">🗑</button>
   <div class="in"><p class="tt">${esc(x.title)}</p><p class="pw">${esc(x.prompt||'')}</p><span class="tm">${fmt(x.dur)}</span></div>`;
  const del=c.querySelector('.deltoday');
  let cdState=null;
  del.onclick=async(ev)=>{ ev.stopPropagation();
   if(!cdState){ cdState=true; del.style.transform='scale(1.2)'; del.textContent='✕';
     tx('Tap again to delete "'+(x.title||'song')+'"',false,2400); setTimeout(()=>{cdState=null;del.textContent='🗑';del.style.transform='';},3200); return; }
   cdState=true; del.style.pointerEvents='none';
   try{
     const r=await fetch('/api/song/'+x.id,{method:'DELETE'});
     if(r.ok){ tx('"'+ (x.title||'Song') +'" deleted'); c.remove(); lib(); }
     else { tx('could not delete',false); del.style.pointerEvents=''; del.textContent='🗑'; }
   }catch(e){ tx('delete failed',false); del.style.pointerEvents=''; del.textContent='🗑'; }
  };
  c.onclick=async()=>{ if(cur.job===x.id){} cur.job=x.id;cur.meta=await (await fetch('/api/meta/'+x.id)).json();show('v-main');drawPlayer();$('lyrpan').style.display='none'; };
  g.appendChild(c);
 });
}
eq();lib();
</script>
</body></html>"""

# Replace logo placeholder
_UI = _UI.replace("__LOGO_URL__", LOGO_URL)

@app.get("/")
def index():
    return _UI, 200, {"Content-Type":"text/html; charset=utf-8"}

# ----------------------------- DevX Banner ---------------------------
def render_banner(mission="MAHEN Muse AI MAKER", status="ONLINE"):
    cols = shutil.get_terminal_size(fallback=(80, 24)).columns

    if cols < 55:
        line = "-" * (cols - 2) if cols > 2 else "--"
        out = f"""
{Fore.CYAN}+{line}+
{Fore.RED}  [*] DEV-X 😈 TERMINAL
{Fore.YELLOW}  MISSION : {Fore.WHITE}{mission[:cols-14]}
{Fore.GREEN}  STATUS  : {Fore.WHITE}{status}
{Fore.MAGENTA}  MODE    : MOBILE / COMPACT
{Fore.CYAN}+{line}+{Style.RESET_ALL}"""
    else:
        line = "=" * min(cols, 70)
        out = f"""
{Fore.CYAN}{line}
{Fore.RED}      ██████╗ ███████╗██╗   ██╗      ██╗  ██╗
{Fore.RED}      ██╔══██╗██╔════╝██║   ██║      ╚██╗██╔╝
{Fore.RED}      ██║  ██║█████╗  ██║   ██║█████╗ ╚███╔╝ 
{Fore.RED}      ██║  ██║██╔══╝  ╚██╗ ██╔╝╚════╝ ██╔██╗ 
{Fore.RED}      ██████╔╝███████╗ ╚████╔╝       ██╔╝ ██╗
{Fore.RED}      ╚═════╝ ╚══════╝  ╚═══╝        ╚═╝  ╚═╝
{Fore.CYAN}{line}
{Fore.YELLOW}  MISSION: {mission} | STATUS: {status}
{Fore.WHITE}  LOGIC: {Fore.MAGENTA}  -> ANALYZE -> BUILD -> EXECUTE
{Fore.CYAN}{line}{Style.RESET_ALL}"""
    print(out)
    sys.stdout.flush()

if __name__ == "__main__":
    render_banner(mission="MAHEN Muse MAKER Engine", status="ACTIVE")
    _rescan_cache()
    print(f"  {G}LIVE{X}  http://127.0.0.1:{PORT}    LAN: http://0.0.0.0:{PORT}", flush=True)
    print("  {0}Watching terminal below — account minting, polls and every API step are logged live.{1}\n".format(Y, X), flush=True)
    sys.stdout.flush()
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True, use_reloader=False)