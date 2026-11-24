#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

JARVIS = Path.home() / "jarvis"
sys.path.insert(0, str(JARVIS))
from memory_system import load_memories, remember
from siri_features import active_user

STATIC = Path(__file__).resolve().parent / "static"
MODEL = os.environ.get("SIRI_GEMINI_MODEL", "gemini-flash-lite-latest")
HOST, PORT = "127.0.0.1", 8765

def api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key: return key
    p = Path.home() / ".config/siri/gemini.env"
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError: pass
    return ""

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=str(STATIC), **kw)
    def log_message(self, fmt, *args): print("[SIRI]", fmt % args)
    def sendj(self, code, obj):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(b)
    def body(self):
        n=int(self.headers.get("Content-Length","0"))
        if n>100000: raise ValueError("Request बहुत बड़ा है")
        return json.loads(self.rfile.read(n).decode())
    def do_GET(self):
        p=urlparse(self.path).path
        uid=active_user()
        if p=="/api/update-check":
            try:
                import urllib.request
                import json
                url = "https://raw.githubusercontent.com/kumarakhil4213-maker/Siri-ai/main/version.json"
                req = urllib.request.Request(url, headers={"User-Agent": "SIRI"})
                with urllib.request.urlopen(req, timeout=15) as response:
                    latest = json.loads(response.read().decode("utf-8"))
                current = json.loads((Path(__file__).resolve().parent / "version.json").read_text(encoding="utf-8"))
                return self.sendj(200, {
                    "current_version": current.get("version"),
                    "latest_version": latest.get("version"),
                    "update_available": current.get("version") != latest.get("version")
                })
            except Exception as e:
                return self.sendj(503, {"error": "Update check failed", "detail": str(e)})
        if p=="/api/status":
            return self.sendj(200,{"key_saved":bool(api_key()),"account_logged_in":bool(uid),"model":MODEL})
        if p=="/api/memories":
            if not uid: return self.sendj(401,{"error":"पहले Termux में SIRI अकाउंट लॉगिन करें।"})
            return self.sendj(200,{"items":load_memories(uid)})
        if p=="/": self.path="/index.html"
        return super().do_GET()
    def do_POST(self):
        p=urlparse(self.path).path
        try: d=self.body()
        except Exception as e: return self.sendj(400,{"error":str(e)})
        uid=active_user()
        if p=="/api/memory":
            if not uid: return self.sendj(401,{"error":"पहले Termux में SIRI अकाउंट लॉगिन करें।"})
            t=str(d.get("text","")).strip()
            if not t: return self.sendj(400,{"error":"याद रखने के लिए कुछ लिखिए।"})
            msg=remember(uid,t[:2000])
            return self.sendj(200,{"message":msg,"items":load_memories(uid)})
        if p=="/api/chat":
            q=str(d.get("message","")).strip()
            if not q: return self.sendj(400,{"error":"सवाल खाली है।"})
            key=api_key()
            if not key: return self.sendj(503,{"error":"Gemini API Key नहीं मिली।"})
            saved=load_memories(uid) if uid else []
            saved_text=[x.get("information","") if isinstance(x,dict) else str(x) for x in saved]
            system=("तुम SIRI हो। सरल हिंदी में जवाब दो। सुरक्षित और ईमानदार रहो। "
                    "उपयोगकर्ता की सेव की गई यादें:\n"+"\n".join("- "+x for x in saved_text))
            contents=[]
            for m in (d.get("history",[]) or [])[-10:]:
                role="model" if m.get("role")=="assistant" else "user"
                t=str(m.get("text",""))[:4000]
                if t: contents.append({"role":role,"parts":[{"text":t}]})
            contents.append({"role":"user","parts":[{"text":q[:5000]}]})
            payload={"system_instruction":{"parts":[{"text":system}]},"contents":contents,
                     "generationConfig":{"temperature":0.7,"maxOutputTokens":2048}}
            req=urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
                data=json.dumps(payload).encode(),
                headers={"Content-Type":"application/json","x-goog-api-key":key},method="POST")
            try:
                with urllib.request.urlopen(req,timeout=90) as r: result=json.loads(r.read())
                parts=result.get("candidates",[{}])[0].get("content",{}).get("parts",[])
                answer="\n".join(x.get("text","") for x in parts if x.get("text"))
                return self.sendj(200,{"answer":answer or "Gemini से खाली जवाब मिला।"})
            except urllib.error.HTTPError as e:
                return self.sendj(502,{"error":f"Gemini API त्रुटि {e.code}: "+e.read().decode("utf-8","replace")[:900]})
            except Exception as e: return self.sendj(502,{"error":"Gemini कनेक्शन समस्या: "+str(e)})
        return self.sendj(404,{"error":"API नहीं मिली"})

if __name__=="__main__":
    print("SIRI: http://127.0.0.1:8765")
    print("Gemini API Key:", "मिली" if api_key() else "नहीं मिली")
    print("SIRI अकाउंट:", "लॉगिन है" if active_user() else "लॉगिन नहीं है")
    print("Ctrl+C से बंद करें")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
