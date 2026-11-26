import os
import hmac
import time
import threading
import requests
from flask import Flask, request
app = Flask(__name__)
history = {}
TTL = 86400

def expire_history():
    now = time.monotonic()
    for key, (stamp, _) in list(history.items()):
        if now - stamp >= TTL:
            history.pop(key, None)
    timer = threading.Timer(60, expire_history)
    timer.daemon = True
    timer.start()

expire_history()
def tg(method, data):
    r = requests.post("https://api.telegram.org/bot"+os.environ["BOT_TOKEN"]+"/"+method, json=data, timeout=10)
    if not r.ok: raise RuntimeError("Telegram request failed")
    return r.json()["result"]

@app.get("/")
def health():
    return "Nexora bot online"

@app.post("/webhook")
def webhook():
    if not hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token",""), os.environ["WEBHOOK_SECRET"]):
        return "", 403
    m = (request.get_json() or {}).get("business_message", {})
    cid = m.get("business_connection_id")
    if not cid or not m.get("text") or m.get("sender_business_bot") or m.get("from",{}).get("is_bot"):
        return "", 200
    c = tg("getBusinessConnection", {"business_connection_id":cid})
    if not c.get("is_enabled") or not c.get("rights",{}).get("can_reply") or m.get("from",{}).get("id")==c["user"]["id"]:
        return "", 200
    chat = m["chat"]["id"]
    if str(chat) not in os.environ.get("ALLOWED_CHAT_IDS","").replace(" ","").split(","):
        return "", 200
    prompt = "You are the disclosed AI assistant of Nexora Ads (nexoraads.online). Reply in the customer's language. Website services only: landing from EUR 150, business website from EUR 300, store from EUR 600, redesign from EUR 100. Ask one relevant question. Never invent prices, commitments or deadlines. Refer complex requests to the owner. Do not request sensitive information."
    key = (cid, chat)
    stamp, previous = history.get(key, (0, []))
    if time.monotonic() - stamp >= TTL:
        previous = []
    current = {"role":"user","content":m["text"][:4000]}
    try:
        r = requests.post(os.environ["AI_API_URL"], headers={"Authorization":"Bearer "+os.environ["AI_API_KEY"]}, json={"model":os.environ["AI_MODEL"],"messages":[{"role":"system","content":prompt}] + previous + [current]}, timeout=(5, 45))
    except requests.exceptions.RequestException as exc:
        app.logger.warning('AI API request failed: %s', type(exc).__name__)
        return '', 503
    if not r.ok:
        app.logger.warning("AI API HTTP status %s", r.status_code)
        return "", 503
    answer = r.json()["choices"][0]["message"]["content"]
    tg("sendMessage", {"business_connection_id":cid,"chat_id":chat,"text":answer[:4000]})
    history[key] = (time.monotonic(), (previous + [current, {"role":"assistant","content":answer[:4000]}])[-20:])
    return "", 200
