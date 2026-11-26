import os
import hmac
import requests
from flask import Flask, request
app = Flask(__name__)
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
    r = requests.post(os.environ["AI_API_URL"], headers={"Authorization":"Bearer "+os.environ["AI_API_KEY"]}, json={"model":os.environ["AI_MODEL"],"messages":[{"role":"system","content":prompt},{"role":"user","content":m["text"][:4000]}]}, timeout=20)
    if not r.ok: return "", 503
    answer = r.json()["choices"][0]["message"]["content"]
    tg("sendMessage", {"business_connection_id":cid,"chat_id":chat,"text":answer[:4000]})
    return "", 200
