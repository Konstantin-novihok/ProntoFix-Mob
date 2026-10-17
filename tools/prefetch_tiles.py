"""
Подготовка ОФЛАЙН-карты: скачивает тайлы нужной области в папку, которую приложение использует в режиме «Офлайн-карта».
Папку затем копируют на телефон в <папка_приложения>/offline_tiles (или укажите offline_dir в конфиге сервера).

Пример (свой тайл-сервер или источник, лицензия которого ЭТО РАЗРЕШАЕТ):
  python tools_prefetch_tiles.py --url "https://tiles.mycompany.com/{z}/{x}/{y}.png" \
      --bbox 50.30 30.35 50.60 30.75 --zmin 10 --zmax 16 --out ./offline_tiles

ВАЖНО: массовая загрузка запрещена условиями Google Maps и публичного сервера OpenStreetMap.
Используйте собственный сервер тайлов (например, из MBTiles/OSM-данных через tileserver-gl) или лицензированный источник.
"""
import argparse
import math
import os
import time

import requests


def tile_xy(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("LAT1", "LON1", "LAT2", "LON2"))
ap.add_argument("--zmin", type=int, default=10)
ap.add_argument("--zmax", type=int, default=16)
ap.add_argument("--out", default="./offline_tiles")
ap.add_argument("--key", default="offline")
ap.add_argument("--limit", type=int, default=20000)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
lat1, lon1, lat2, lon2 = a.bbox
jobs = []
for z in range(a.zmin, a.zmax + 1):
    x1, y1 = tile_xy(max(lat1, lat2), min(lon1, lon2), z)
    x2, y2 = tile_xy(min(lat1, lat2), max(lon1, lon2), z)
    jobs += [(z, x, y) for x in range(x1, x2 + 1) for y in range(y1, y2 + 1)]
print("tiles:", len(jobs))
if len(jobs) > a.limit:
    raise SystemExit("Слишком много тайлов — уменьшите область/zoom или поднимите --limit")
for i, (z, x, y) in enumerate(jobs, 1):
    # MapView хранит в имени файла Y, ПЕРЕВЁРНУТЫЙ относительно стандартных XYZ-тайлов (Y_map = 2^z - 1 - Y_xyz)
    fn = os.path.join(a.out, f"{a.key}_{z}_{x}_{2 ** z - 1 - y}.png")
    if os.path.exists(fn):
        continue
    r = requests.get(a.url.format(z=z, x=x, y=y), headers={"User-Agent": "HomeMaster-offline/1.0"}, timeout=20)
    if r.ok:
        open(fn, "wb").write(r.content)
    time.sleep(0.1)
    if i % 200 == 0:
        print(i, "/", len(jobs))
print("done")
