"""
Провайдеры карт. Приложение не привязано к одной карте: источник выбирается по имени.

  google  — официальный Google Map Tiles API (нужен ключ GOOGLE_MAPS_KEY на сервере; без ключа — запасной OSM)
  osm     — OpenStreetMap (для разработки; для продакшена поднимите свой тайл-сервер)
  custom  — ваш онлайн-сервер тайлов по шаблону URL, например  https://tiles.mycompany.com/{z}/{x}/{y}.png
  offline — готовые тайлы на устройстве (см. tools/prefetch_tiles.py), интернет не нужен

ЧТОБЫ ДОБАВИТЬ СВОЙ ПРОВАЙДЕР: напишите функцию  def _mine(cfg, done): ... done(MapSource(...))
и добавьте её в словарь PROVIDERS внизу. Больше ничего менять не нужно.
"""
import os
import threading

import requests
from kivy.clock import Clock
from kivy_garden.mapview import MapSource

LANG = {"ru": "ru-RU", "uk": "uk-UA", "en": "en-US", "pt": "pt-BR"}


def _osm(cfg, done):
    done(MapSource(url="https://tile.openstreetmap.org/{z}/{x}/{y}.png", cache_key="osm", subdomains="",
                   max_zoom=19, attribution="© OpenStreetMap contributors"))


def _google(cfg, done):
    """Google Map Tiles API: сначала создаётся сессия, затем тайлы берутся по её номеру."""
    key = cfg.get("google_maps_key")
    if not key:
        return _osm(cfg, done)

    def work():
        try:
            lang = LANG.get(cfg.get("lang"), "en-US")
            r = requests.post("https://tile.googleapis.com/v1/createSession", params={"key": key}, timeout=15,
                              json={"mapType": "roadmap", "language": lang, "region": lang[-2:]})
            r.raise_for_status()
            session = r.json()["session"]
            src = MapSource(url="https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}?session=" + session + "&key=" + key,
                            cache_key="google_" + session[:8], subdomains="", min_zoom=0, max_zoom=22,
                            attribution="Map data © Google")
            Clock.schedule_once(lambda dt: done(src))
        except Exception:   # нет сети/ключ неверный → запасной вариант
            Clock.schedule_once(lambda dt: _osm(cfg, done))
    threading.Thread(target=work, daemon=True).start()


def _custom(cfg, done):
    url = cfg.get("custom_tile_url")
    if not url:
        return _osm(cfg, done)
    done(MapSource(url=url, cache_key="custom", subdomains="", max_zoom=int(cfg.get("max_zoom", 19)),
                   attribution=cfg.get("attribution", "")))


def _offline(cfg, done):
    """Тайлы лежат в папке как  offline_<z>_<x>_<y>.png  (их создаёт tools/prefetch_tiles.py; Y в имени перевёрнут относительно XYZ).
    MapView берёт их из кэша; ссылка-заглушка никогда не запрашивается, если тайл есть."""
    folder = cfg.get("offline_dir") or os.path.join(cfg.get("cache_root", "."), "offline_tiles")
    os.makedirs(folder, exist_ok=True)
    done(MapSource(url="http://127.0.0.1:9/{z}/{x}/{y}.png", cache_key="offline", subdomains="",
                   max_zoom=int(cfg.get("max_zoom", 17)), cache_dir=folder, attribution="Offline map"))


PROVIDERS = {"google": _google, "osm": _osm, "custom": _custom, "offline": _offline}


def build_source(provider, cfg, done):
    PROVIDERS.get(provider, _osm)(cfg, done)
