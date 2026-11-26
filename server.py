#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.error
import time
import shutil
import re
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

JARVIS = Path.home() / "jarvis"
sys.path.insert(0, str(JARVIS))
from memory_system import load_memories, remember
ACTIVE_FILE = JARVIS / "data" / "active_user.txt"

def active_user():
    try:
        return ACTIVE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""

STATIC = Path(__file__).resolve().parent / "static"
MODEL = os.environ.get("SIRI_GEMINI_MODEL", "gemini-flash-lite-latest")
HOST, PORT = "127.0.0.1", 8765
REPAIR_PENDING = {}

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
        if p=="/download/Siri.apk":
            apk = Path(__file__).resolve().parent / "downloads" / "Siri.apk"
            if not apk.is_file():
                return self.sendj(404, {"error": "Siri APK नहीं मिली"})
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.android.package-archive")
            self.send_header("Content-Length", str(apk.stat().st_size))
            self.send_header("Content-Disposition", 'attachment; filename="Siri.apk"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with apk.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return
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
        if p=="/api/self-check":
            checks = {}
            checks["gemini_api_key"] = bool(api_key())
            checks["account_login"] = bool(uid)
            checks["memory_module"] = Path(JARVIS / "memory_system.py").is_file()
            checks["update_module"] = (Path(__file__).resolve().parent / "update_system.py").is_file()
            checks["frontend"] = (Path(__file__).resolve().parent / "static" / "index.html").is_file()
            checks["backup_directory"] = (Path(__file__).resolve().parent / "updates" / "backups").is_dir()
            try:
                checks["memory_access"] = bool(uid) and isinstance(load_memories(uid), list)
            except Exception:
                checks["memory_access"] = False
            passed = sum(checks.values())
            return self.sendj(200, {"checks": checks, "passed": passed, "total": len(checks), "all_ok": all(checks.values())})
        if p=="/api/status":
            return self.sendj(200,{"key_saved":bool(api_key()),"account_logged_in":bool(uid),"model":MODEL})
        if p=="/api/memories":
            if not uid: return self.sendj(401,{"error":"पहले Termux में SIRI अकाउंट लॉगिन करें।"})
            return self.sendj(200,{"items":load_memories(uid)})
        if p=="/api/backups":
            import importlib.util
            update_path = Path(__file__).resolve().parent / "update_system.py"
            spec = importlib.util.spec_from_file_location("siri_web_update_system", update_path)
            if spec is None or spec.loader is None:
                return self.sendj(500, {"error": "Backup module नहीं मिला"})
            update_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(update_module)
            verify_backup = update_module.verify_backup
            root = Path(__file__).resolve().parent / "updates" / "backups"
            items = []
            if root.is_dir():
                for item in sorted(root.iterdir(), reverse=True):
                    if item.name.startswith("siri_backup_") and item.is_dir() and not item.is_symlink():
                        manifest = (item / "SHA256SUMS.json").is_file()
                        items.append({
                            "name": item.name,
                            "sha256_verified": bool(verify_backup(item)),
                            "has_manifest": manifest
                        })
            return self.sendj(200, {"items": items})
        if p=="/": self.path="/index.html"
        return super().do_GET()
    def do_POST(self):
        p=urlparse(self.path).path
        try: d=self.body()
        except Exception as e: return self.sendj(400,{"error":str(e)})
        uid=active_user()
        if p=="/api/repair-diagnose":
            checks = {
                "gemini_api_key": bool(api_key()),
                "account_login": bool(uid),
                "memory_module": (JARVIS / "memory_system.py").is_file(),
                "update_module": (Path(__file__).resolve().parent / "update_system.py").is_file(),
                "frontend": (Path(__file__).resolve().parent / "static" / "index.html").is_file(),
                "backup_directory": (Path(__file__).resolve().parent / "updates" / "backups").is_dir()
            }
            try:
                checks["memory_access"] = bool(uid) and isinstance(load_memories(uid), list)
            except Exception:
                checks["memory_access"] = False
            failed = [k for k, v in checks.items() if not v]
            suggestions = {
                "gemini_api_key": "Gemini API Key की सेटिंग जाँचें।",
                "account_login": "SIRI अकाउंट में लॉगिन करें।",
                "memory_module": "पुराने JARVIS memory module का path जाँचें।",
                "update_module": "SIRI update module की मौजूदगी जाँचें।",
                "frontend": "static/index.html की मौजूदगी जाँचें।",
                "backup_directory": "Backup directory की स्थिति जाँचें।",
                "memory_access": "Memory module और अकाउंट access जाँचें।"
            }
            return self.sendj(200, {
                "mode": "read_only",
                "checks": checks,
                "failed": failed,
                "suggestions": [suggestions[k] for k in failed],
                "repair_requires_approval": True
            })
        if p=="/api/repair-plan":
            checks = {
                "gemini_api_key": bool(api_key()),
                "account_login": bool(uid),
                "memory_module": (JARVIS / "memory_system.py").is_file(),
                "update_module": (Path(__file__).resolve().parent / "update_system.py").is_file(),
                "frontend": (Path(__file__).resolve().parent / "static" / "index.html").is_file(),
                "backup_directory": (Path(__file__).resolve().parent / "updates" / "backups").is_dir(),
                "memory_access": bool(uid) and (JARVIS / "memory_system.py").is_file()
            }
            actions = {
                "gemini_api_key": "Gemini API key configuration जाँचें।",
                "account_login": "SIRI अकाउंट में लॉगिन करें।",
                "memory_module": "Memory module की उपलब्धता और import जाँचें।",
                "update_module": "Update module की उपलब्धता जाँचें।",
                "frontend": "Frontend file की उपलब्धता जाँचें।",
                "backup_directory": "Backup directory सुरक्षित रूप से बनाएँ या जाँचें।",
                "memory_access": "Memory और account access की जाँच करें।"
            }
            failed = [k for k, ok in checks.items() if not ok]
            plan = [{"check": k, "proposed_action": actions[k],
                     "requires_approval": True} for k in failed]
            plan_id = os.urandom(16).hex() if failed and uid else ""
            if plan_id:
                REPAIR_PENDING[uid] = {"plan_id": plan_id, "plan": plan, "created_at": time.time()}
            elif uid:
                REPAIR_PENDING.pop(uid, None)
            return self.sendj(200, {
                "mode": "read_only_plan",
                "checks": checks,
                "failed": failed,
                "plan": plan,
                "plan_id": plan_id,
                "message": "कोई खराबी नहीं मिली।" if not failed else "Repair से पहले आपकी अनुमति आवश्यक है।",
                "repair_requires_approval": True
            })
        if p=="/api/repair-approve":
            if not uid:
                return self.sendj(401, {"error": "पहले SIRI अकाउंट लॉगिन करें।"})
            pending = REPAIR_PENDING.get(uid)
            plan_id = str(d.get("plan_id", ""))
            backup_name = str(d.get("backup_name", ""))
            if not pending or not plan_id or plan_id != pending["plan_id"]:
                return self.sendj(409, {"error": "Repair Plan नहीं मिला या पुराना हो चुका है।"})
            created_at = pending.get("created_at", 0)
            if not isinstance(created_at, (int, float)) or time.time() - created_at > 600 or time.time() < created_at:
                REPAIR_PENDING.pop(uid, None)
                return self.sendj(409, {"error": "Repair Plan की समय-सीमा समाप्त हो गई है। नया Plan बनाएँ।"})
            if pending.get("approved"):
                return self.sendj(409, {"error": "इस Repair Plan का Approval पहले ही इस्तेमाल हो चुका है।"})
            if not pending["plan"]:
                return self.sendj(400, {"error": "खाली Repair Plan approve नहीं हो सकता।"})
            if not re.fullmatch(r"siri_backup_\d{8}_\d{6}", backup_name):
                return self.sendj(400, {"error": "Backup का नाम अमान्य है।"})
            try:
                import importlib.util
                base = Path(__file__).resolve().parent
                backups_dir = base / "updates" / "backups"
                target = backups_dir / backup_name
                if (not backups_dir.is_dir() or target.is_symlink()
                        or not target.is_dir()
                        or target.resolve().parent != backups_dir.resolve()
                        or not (target / "BACKUP_COMPLETE.txt").is_file()
                        or (target / "BACKUP_COMPLETE.txt").is_symlink()):
                    return self.sendj(400, {"error": "सुरक्षित Verified Backup नहीं मिला।"})
                update_path = base / "update_system.py"
                spec = importlib.util.spec_from_file_location("siri_approval_backup_module", update_path)
                if spec is None or spec.loader is None:
                    return self.sendj(500, {"error": "Backup verification module नहीं मिला।"})
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if not module.verify_backup(target):
                    return self.sendj(400, {"error": "Backup SHA-256 Verification असफल।"})
                pending["approved"] = True
                pending["backup_name"] = backup_name
                pending["sha256_verified"] = True
                return self.sendj(200, {
                    "message": "Approval सुरक्षित रूप से दर्ज हुआ।",
                    "plan": pending["plan"],
                    "backup_name": backup_name,
                    "sha256_verified": True,
                    "repair_executed": False
                })
            except Exception as e:
                return self.sendj(500, {"error": str(e)})
        if p=="/api/backup":
            if not uid:
                return self.sendj(401,{"error":"पहले SIRI अकाउंट लॉगिन करें।"})
            try:
                import importlib.util
                update_path = Path(__file__).resolve().parent / "update_system.py"
                spec = importlib.util.spec_from_file_location("siri_backup_module", update_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError("Backup module नहीं मिला")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                backup_path = Path(module.create_backup())
                verified = bool(module.verify_backup(backup_path))
                if not verified:
                    return self.sendj(500,{"error":"Backup बना, लेकिन SHA-256 Verification असफल रहा।","name":backup_path.name})
                return self.sendj(201,{"message":"Backup और SHA-256 Verification सफल।","name":backup_path.name,"sha256_verified":True})
            except Exception as e:
                return self.sendj(500,{"error":str(e)})
        if p=="/api/delete-backup":
            if not uid:
                return self.sendj(401, {"error": "पहले SIRI अकाउंट लॉगिन करें।"})
            name = d.get("name", "") if isinstance(d, dict) else ""
            if not isinstance(name, str) or not re.fullmatch(r"siri_backup_\d{8}_\d{6}", name):
                return self.sendj(400, {"error": "Backup का नाम अमान्य है।"})
            backups_dir = Path(__file__).resolve().parent / "updates" / "backups"
            target = backups_dir / name
            try:
                if not backups_dir.is_dir() or target.is_symlink() or not target.is_dir():
                    return self.sendj(404, {"error": "Backup folder नहीं मिला।"})
                if target.resolve().parent != backups_dir.resolve():
                    return self.sendj(400, {"error": "असुरक्षित Backup path।"})
                shutil.rmtree(target)
                return self.sendj(200, {"message": "Backup सफलतापूर्वक Delete हुआ।", "name": name})
            except Exception as e:
                return self.sendj(500, {"error": str(e)})
        if p=="/api/restore-backup":
            if not uid:
                return self.sendj(401, {"error": "पहले SIRI अकाउंट लॉगिन करें।"})
            name = d.get("name", "") if isinstance(d, dict) else ""
            if not isinstance(name, str) or not re.fullmatch(r"siri_backup_\d{8}_\d{6}", name):
                return self.sendj(400, {"error": "Backup का नाम अमान्य है।"})
            backups_dir = Path(__file__).resolve().parent / "updates" / "backups"
            target = backups_dir / name
            try:
                if not backups_dir.is_dir() or target.is_symlink() or not target.is_dir():
                    return self.sendj(404, {"error": "Backup folder नहीं मिला।"})
                if target.resolve().parent != backups_dir.resolve():
                    return self.sendj(400, {"error": "असुरक्षित Backup path।"})
                marker_file = target / "BACKUP_COMPLETE.txt"
                manifest = target / "SHA256SUMS.json"
                if marker_file.is_symlink() or not marker_file.is_file():
                    return self.sendj(400, {"error": "Backup अधूरा है।"})
                if manifest.is_symlink() or not manifest.is_file():
                    return self.sendj(400, {"error": "SHA-256 manifest नहीं मिला।"})
                import importlib.util
                update_path = Path(__file__).resolve().parent / "update_system.py"
                spec = importlib.util.spec_from_file_location("siri_restore_verify", update_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError("Backup verification module नहीं मिला।")
                verifier = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(verifier)
                if not verifier.verify_backup(target):
                    return self.sendj(400, {"error": "SHA-256 verification विफल। Restore रोक दिया गया।"})
                rollback_path = Path(__file__).resolve().parent / "rollback.py"
                rspec = importlib.util.spec_from_file_location("siri_restore_module", rollback_path)
                if rspec is None or rspec.loader is None:
                    raise RuntimeError("Restore module नहीं मिला।")
                rollback = importlib.util.module_from_spec(rspec)
                rspec.loader.exec_module(rollback)
                rollback.restore(name)
                return self.sendj(200, {"message": "Restore सफल हुआ। सुरक्षा Backup भी बनाया गया।", "name": name})
            except Exception as e:
                return self.sendj(500, {"error": str(e)})
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
