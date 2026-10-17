"""
Клиент REST API сервера. Все запросы идут в отдельном потоке (чтобы интерфейс не «замерзал»),
результат возвращается в главный поток Kivy через Clock.schedule_once.
"""
import mimetypes
import os
import threading

import requests
from kivy.clock import Clock


class Api:
    def __init__(self):
        self.base = ""     # адрес сервера, например https://service.example.com
        self.token = None  # JWT после входа

    def url(self, path):
        return self.base.rstrip("/") + path

    def media_url(self, mid):
        """Ссылка на файл (токен в параметре — чтобы AsyncImage мог загрузить картинку)."""
        return self.url(f"/media/{mid}?token={self.token}")

    def _run(self, method, path, ok, err, **kw):
        def work():
            try:
                headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
                r = requests.request(method, self.url(path), headers=headers, timeout=60, **kw)
                if r.status_code >= 400:
                    try:
                        msg = r.json().get("detail", r.text)
                    except Exception:
                        msg = r.text
                    Clock.schedule_once(lambda dt, m=str(msg): err and err(m))
                else:
                    data = r.json()
                    Clock.schedule_once(lambda dt, d=data: ok and ok(d))
            except Exception as e:
                Clock.schedule_once(lambda dt, m=str(e): err and err(m))
        threading.Thread(target=work, daemon=True).start()

    def get(self, path, ok=None, err=None):
        self._run("GET", path, ok, err)

    def post(self, path, body=None, ok=None, err=None):
        self._run("POST", path, ok, err, json=body or {})

    def patch(self, path, body, ok=None, err=None):
        self._run("PATCH", path, ok, err, json=body)

    def upload(self, path, filepath, ok=None, err=None):
        """Загрузка фото/видео (multipart)."""
        def work():
            try:
                mime = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
                with open(filepath, "rb") as f:
                    r = requests.post(self.url(path), headers={"Authorization": f"Bearer {self.token}"},
                                      files={"file": (os.path.basename(filepath), f, mime)}, timeout=600)
                if r.status_code >= 400:
                    Clock.schedule_once(lambda dt, m=r.text: err and err(m))
                else:
                    Clock.schedule_once(lambda dt, d=r.json(): ok and ok(d))
            except Exception as e:
                Clock.schedule_once(lambda dt, m=str(e): err and err(m))
        threading.Thread(target=work, daemon=True).start()
