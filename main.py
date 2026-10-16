"""
Home Master — Android-клиент (Kivy). Работает с сервером из ../server.
Структура файла:
  1. Константы (роли, навигация)
  2. Вспомогательные виджеты (Nav, экраны)
  3. Класс ServiceApp: вход, списки, карточка заказа, карта, пользователи, настройки
Разметка интерфейса — в ui.kv, переводы — в locales/*.json.
"""
import json
import os
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import escape_markup, platform
from kivy_garden.mapview import MapMarker, MapView  # noqa: F401  (MapView нужен разметке ui.kv)

from api import Api
from camera import CameraScreen
from i18n import I18n
from maps import build_source

HERE = os.path.dirname(os.path.abspath(__file__))

# ───────────── 1. Константы ─────────────
OWNER, HEAD, EXECUTOR, CLIENT, STAFF, OBSERVER = 1, 2, 3, 4, 5, 6
ROLE_KEYS = {1: "role_owner", 2: "role_head", 3: "role_executor", 4: "role_client", 5: "role_staff", 6: "role_observer"}
STATUSES = ["new", "assigned", "accepted", "in_progress", "estimate", "done", "cancelled"]

# Меню: (экран, ключ перевода, какие роли видят пункт). Чтобы добавить раздел — допишите строку.
NAV = [
    ("orders", "orders", {1, 2, 3, 4, 5, 6}),
    ("order_new", "new_order", {1, 2, 4, 5}),
    ("users", "users", {1, 2, 4}),
    ("departments", "departments", {1}),
    ("audit", "history", {1}),
    ("settings", "settings", {1, 2, 3, 4, 5, 6}),
]
NAVS = []  # все созданные меню — чтобы перерисовать при смене языка/входе


# ───────────── 2. Виджеты и экраны ─────────────
class Nav(ScrollView):
    """Горизонтальное меню; пункты зависят от роли пользователя."""

    def __init__(self, **kw):
        super().__init__(size_hint_y=None, height=dp(48), do_scroll_y=False, **kw)
        self.box = GridLayout(rows=1, size_hint_x=None, spacing=dp(4))
        self.box.bind(minimum_width=self.box.setter("width"))
        self.add_widget(self.box)
        NAVS.append(self)
        Clock.schedule_once(lambda dt: self.rebuild())

    def rebuild(self):
        app = App.get_running_app()
        self.box.clear_widgets()
        role = app.me["role"] if app.me else None
        for screen, key, roles in NAV:
            if role in roles:
                b = Button(text=app.t(key), size_hint_x=None, width=dp(140))
                b.bind(on_release=lambda *_a, s=screen: App.get_running_app().go(s))
                self.box.add_widget(b)


class ListScreen(Screen):
    title = StringProperty("")


class LoginScreen(Screen):
    pass


class RegisterScreen(Screen):
    pass


class OrderScreen(Screen):
    pass


class OrderNewScreen(Screen):
    pass


class MapScreen(Screen):
    pass


# ───────────── 3. Приложение ─────────────
def crash_view(text):
    """Экран с текстом ошибки (можно выделить и переслать разработчику)."""
    box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    box.add_widget(Label(text="Home Master: ERROR", size_hint_y=None, height=dp(36), bold=True, color=(1, .4, .4, 1)))
    ti = TextInput(text=text, readonly=True, font_size="12sp")
    box.add_widget(ti)
    return box


def _install_exception_popup():
    """Ошибки внутри кнопок и обработчиков показываем окном с текстом, а не молча «глотаем»."""
    from kivy.base import ExceptionHandler, ExceptionManager

    class Handler(ExceptionHandler):
        def handle_exception(self, inst):
            import traceback
            try:
                box = BoxLayout(orientation="vertical", padding=dp(6))
                box.add_widget(TextInput(text="".join(traceback.format_exception(type(inst), inst, inst.__traceback__)),
                                         readonly=True, font_size="11sp"))
                b = Button(text="OK", size_hint_y=None, height=dp(44))
                box.add_widget(b)
                pop = Popup(title="Error", content=box, size_hint=(.96, .8))
                b.bind(on_release=pop.dismiss)
                pop.open()
            except Exception:
                pass
            return ExceptionManager.PASS
    ExceptionManager.add_handler(Handler())


class ServiceApp(App):
    lang = StringProperty("ru")
    tr = ObjectProperty(lambda key: key)       # функция перевода; меняется при смене языка → UI обновляется
    server_url = StringProperty("https://service.example.com")
    me = ObjectProperty(None, allownone=True)  # текущий пользователь (словарь с сервера)
    can_pick_client = BooleanProperty(False)   # владелец/начальник может создать заказ от имени заказчика

    # ----- запуск -----
    def build(self):
        """Если запуск упал — показываем текст ошибки на экране (на телефоне иначе приложение просто закроется)."""
        try:
            return self._build()
        except Exception:
            import traceback
            return crash_view(traceback.format_exc())

    def _build(self):
        _install_exception_popup()
        self.i18n = I18n(os.path.join(HERE, "locales"))
        self.api = Api()
        self.cfg_path = os.path.join(self.user_data_dir, "settings.json")
        self.cfg = {}
        try:
            self.cfg = json.load(open(self.cfg_path, encoding="utf-8"))
        except Exception:
            pass
        self.server_url = self.cfg.get("server", self.server_url)
        self.set_lang(self.cfg.get("lang", "ru"))
        self.new = {}          # черновик нового заказа
        self.reg = {"files": [], "lat": None, "lon": None}   # черновик регистрации
        self.map_cfg = {}      # настройки карт с сервера (/config)
        self._map_src = None   # текущий источник карты (создаётся лениво)
        self.loc_target = "new"
        self.cam_cb, self.cam_back = None, "login"
        self.cur_order_id = None
        self.map_ctx = {}
        Builder.load_file(os.path.join(HERE, "ui.kv"))
        sm = ScreenManager()
        sm.add_widget(LoginScreen())
        sm.add_widget(RegisterScreen())
        for name in ("orders", "users", "departments", "audit", "settings"):
            sm.add_widget(ListScreen(name=name))
        sm.add_widget(OrderScreen())
        sm.add_widget(OrderNewScreen())
        sm.add_widget(MapScreen())
        sm.add_widget(CameraScreen(self))
        Window.bind(on_keyboard=self.on_back_key)
        return sm

    def on_start(self):
        try:  # Android 6+: запрос разрешений во время работы
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.READ_EXTERNAL_STORAGE,
                                 Permission.CAMERA])
        except ImportError:
            pass
        self.fetch_map_config()
        if self.cfg.get("token"):  # автоматический вход по сохранённому токену
            self.api.base, self.api.token = self.server_url, self.cfg["token"]
            self.api.get("/me", lambda u: self.after_login(u), lambda e: None)

    def on_back_key(self, window, key, *args):
        if key == 27:  # кнопка «назад» на Android
            if self.root.current in ("login", "orders"):
                return False
            self.go("orders" if self.me else "login")
            return True

    # ----- язык и настройки -----
    def t(self, key):
        return self.tr(key)

    def set_lang(self, code):
        self.lang = code
        self.tr = lambda key, _c=code: self.i18n.t(key, _c)
        self.cfg["lang"] = code
        self.save_cfg()
        for n in NAVS:
            n.rebuild()

    def save_cfg(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            json.dump(self.cfg, open(self.cfg_path, "w", encoding="utf-8"))
        except Exception:
            pass

    def pick_language(self):
        self.pick(self.t("language"), [(n, c) for c, n in self.i18n.languages()], self.set_lang)

    # ----- универсальные помощники интерфейса -----
    def go(self, name):
        """Перейти на экран и загрузить его данные (метод load_<имя>)."""
        self.root.current = name
        getattr(self, "load_" + name, lambda: None)()

    def info(self, text, title=None):
        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        lb = Factory.Lbl(text=escape_markup(str(text)))
        box.add_widget(lb)
        b = Factory.Btn(text=self.t("ok"))
        box.add_widget(b)
        pop = Popup(title=title or "", content=box, size_hint=(.9, .5))
        b.bind(on_release=pop.dismiss)
        pop.open()

    def error(self, msg):
        self.info(msg, self.t("error"))

    def fill(self, grid, items):
        """items: [(текст, действие)] → список кнопок-строк."""
        grid.clear_widgets()
        if not items:
            grid.add_widget(Factory.Lbl(text=self.t("no_data")))
        for text, cb in items:
            b = Factory.Row(text=text)
            if cb:
                b.bind(on_release=lambda *_a, cb=cb: cb())
            grid.add_widget(b)

    def pick(self, title, options, callback):
        """Окно выбора. options: [(подпись, значение)] → callback(значение)."""
        box = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        sv, grid = ScrollView(), GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        grid.bind(minimum_height=grid.setter("height"))
        pop = Popup(title=title, content=box, size_hint=(.92, .8))
        for label, value in options:
            b = Factory.Btn(text=str(label))
            b.bind(on_release=lambda *_a, v=value: (pop.dismiss(), callback(v)))
            grid.add_widget(b)
        sv.add_widget(grid)
        box.add_widget(sv)
        c = Factory.Btn(text=self.t("cancel"))
        c.bind(on_release=pop.dismiss)
        box.add_widget(c)
        pop.open()

    def form(self, title, fields, callback):
        """Окно ввода. fields: [(ключ, ключ_перевода, это_пароль)] → callback({ключ: текст})."""
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        inputs = {}
        for key, label, pw in fields:
            ti = TextInput(hint_text=self.t(label), multiline=False, password=pw, size_hint_y=None, height=dp(44))
            inputs[key] = ti
            box.add_widget(ti)
        box.add_widget(Widget_())
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        ok, cancel = Factory.Btn(text=self.t("ok")), Factory.Btn(text=self.t("cancel"))
        row.add_widget(ok)
        row.add_widget(cancel)
        box.add_widget(row)
        pop = Popup(title=title, content=box, size_hint=(.92, None), height=dp(150 + 52 * len(fields)))
        cancel.bind(on_release=pop.dismiss)
        ok.bind(on_release=lambda *_a: (pop.dismiss(), callback({k: v.text for k, v in inputs.items()})))
        pop.open()

    def refresh_current(self):
        getattr(self, "load_" + self.root.current, lambda: None)()

    # ----- вход / регистрация -----
    def login(self, username, password, server):
        self.server_url = server.strip().rstrip("/")
        self.api.base = self.server_url
        self.cfg["server"] = self.server_url
        self.api.post("/auth/login", {"username": username, "password": password}, self.on_auth, self.error)

    # ----- регистрация (заказчик) -----
    def open_register(self, server):
        self.server_url = server.strip().rstrip("/")
        self.api.base = self.server_url
        self.go("register")

    def load_register(self):
        self.reg = {"files": [], "lat": None, "lon": None}
        ids = self.root.get_screen("register").ids
        for k in ("user", "pwd", "fname", "phone", "company", "website", "address", "pnum", "pissued"):
            ids[k].text = ""
        ids.consent.active = False
        self.refresh_reg()
        self.fetch_map_config()

    def refresh_reg(self):
        """Перерисовать строку положения и список приложенных документов."""
        ids = self.root.get_screen("register").ids
        r = self.reg
        ids.loc.text = (f"{self.t('location_set')}: {r['lat']:.5f}, {r['lon']:.5f}" if r["lat"] is not None
                        else self.t("location_none"))
        ids.docs.clear_widgets()
        for path in r["files"]:
            row = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(6))
            if path.lower().endswith((".jpg", ".jpeg")):
                row.add_widget(AsyncImage(source=path, size_hint_x=None, width=dp(64), fit_mode="contain"))
            else:
                row.add_widget(Label(text="PDF", bold=True, size_hint_x=None, width=dp(64)))
            b = Factory.Row(text=f"{escape_markup(os.path.basename(path))}\n[size=12sp]{self.t('tap_remove')}[/size]", height=dp(64))
            b.bind(on_release=lambda *_a, p=path: (r["files"].remove(p), self.refresh_reg()))
            row.add_widget(b)
            ids.docs.add_widget(row)

    def add_reg_files(self, files):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".pdf")):
                self.reg["files"].append(f)
            else:
                self.error(self.t("bad_file_type"))
        self.refresh_reg()

    def pick_reg_location(self):
        r = self.reg
        self.open_map("pick", r["lat"] or 50.4501, r["lon"] or 30.5234, cb=lambda la, lo: self.set_loc("reg", la, lo))

    def do_register(self):
        ids = self.root.get_screen("register").ids
        if len(ids.user.text.strip()) < 3 or len(ids.pwd.text) < 6 or len(ids.fname.text.split()) < 2:
            return self.error(self.t("fill_required"))
        if not ids.consent.active:
            return self.error(self.t("consent_required"))
        body = dict(username=ids.user.text.strip(), password=ids.pwd.text, full_name=ids.fname.text.strip(),
                    phone=ids.phone.text.strip(), company_name=ids.company.text.strip(), website=ids.website.text.strip(),
                    address=ids.address.text.strip(), lat=self.reg["lat"], lon=self.reg["lon"],
                    passport_number=ids.pnum.text.strip(), passport_issued=ids.pissued.text.strip(), consent=True)
        self.api.base = self.server_url
        self.api.post("/auth/register", body, self.on_registered, self.error)

    def on_registered(self, data):
        """Аккаунт создан → загружаем приложенные сканы (JPEG/PDF), затем входим."""
        self.api.token = self.cfg["token"] = data["token"]
        self.save_cfg()
        self.upload_my_docs(list(self.reg["files"]), lambda: self.after_login(data["user"]))

    def upload_my_docs(self, files, done):
        if not files:
            return done()
        path = files.pop(0)

        def next_(_r=None):
            self.upload_my_docs(files, done)

        def failed(msg):
            self.error(msg)
            next_()
        self.api.upload("/me/documents", path, next_, failed)

    def on_auth(self, data):
        self.api.token = data["token"]
        self.cfg["token"] = data["token"]
        self.save_cfg()
        self.after_login(data["user"])

    def after_login(self, user):
        self.me = user
        self.can_pick_client = user["role"] in (OWNER, HEAD)
        for n in NAVS:
            n.rebuild()
        self.go("orders")

    def logout(self):
        self.cfg.pop("token", None)
        self.save_cfg()
        self.api.token, self.me = None, None
        for n in NAVS:
            n.rebuild()
        self.root.current = "login"

    # ----- список заказов -----
    def status_label(self, s):
        return self.t("st_" + s)

    def load_orders(self):
        sc = self.root.get_screen("orders")
        sc.title = self.t("orders")
        sc.ids.actions.clear_widgets()
        b = Factory.Btn(text=self.t("refresh"))
        b.bind(on_release=lambda *_a: self.load_orders())
        sc.ids.actions.add_widget(b)

        def show(orders):
            self.fill(sc.ids.list, [(self.order_line(o), lambda o=o: self.open_order(o["id"])) for o in orders])
        self.api.get("/orders", show, self.error)

    def order_line(self, o):
        return (f"[b]#{o['id']} {escape_markup(o['title'])}[/b]\n"
                f"{self.status_label(o['status'])}  ·  {escape_markup(o['address'] or '')}  ·  "
                f"{escape_markup(o['executor_name'] or '-')}")

    def open_order(self, oid):
        self.cur_order_id = oid
        self.go("order")

    # ----- карточка заказа -----
    def load_order(self):
        self.api.get(f"/orders/{self.cur_order_id}", self.show_order, self.error)

    def show_order(self, d):
        o, role = d["order"], self.me["role"]
        body = self.root.get_screen("order").ids.body
        body.clear_widgets()
        e = escape_markup
        lines = [f"[b]#{o['id']} {e(o['title'])}[/b]",
                 f"{self.t('status')}: {self.status_label(o['status'])}",
                 e(o["description"] or ""),
                 f"{self.t('address')}: {e(o['address'] or '-')}",
                 f"{self.t('department')}: {e(o['department_name'] or '-')}",
                 f"{self.t('client')}: {e(o['client_name'] or '-')}  ({self.t('created_by')}: {e(o['created_by_name'] or '-')})",
                 f"{self.t('executor')}: {e(o['executor_name'] or '-')}"]
        if o["estimate_hours"] is not None:
            lines.append(f"{self.t('estimate')}: {o['estimate_hours']} {self.t('hours')} / {o['estimate_price']}")
        if o["rating"]:
            lines.append(f"{self.t('rating')}: {'*' * o['rating']}")
        body.add_widget(Factory.Lbl(text="\n".join(lines)))

        # --- кнопки действий в зависимости от роли и состояния ---
        def act(key, fn):
            b = Factory.Btn(text=self.t(key))
            b.bind(on_release=lambda *_a: fn(o))
            body.add_widget(b)
        if o["lat"] is not None:
            act("show_map", lambda o: self.show_on_map(o["lat"], o["lon"]))
        if role == EXECUTOR and o["status"] in ("new", "assigned") and o["executor_id"] in (None, self.me["id"]):
            act("accept", lambda o: self.post_order("accept"))
        if role in (OWNER, HEAD) or (role == EXECUTOR and o["executor_id"] == self.me["id"]):
            act("change_status", self.change_status)
        if role in (OWNER, HEAD, EXECUTOR):
            act("estimate", self.ask_estimate)
        if role in (OWNER, HEAD):
            act("assign_executor", self.assign_executor)
        if role == OWNER:
            act("assign_dept", self.assign_department)
        if role == CLIENT and o["status"] == "done":
            act("rate", self.ask_rating)
        if role == CLIENT and o["status"] not in ("done", "cancelled"):
            act("cancel", lambda o: self.post_order("status", {"status": "cancelled"}))
        if role != OBSERVER:
            if role in (OWNER, HEAD, EXECUTOR):
                act("message_client", lambda o: self.ask_comment(True))
                act("comment_internal", lambda o: self.ask_comment(False))
            else:
                act("message", lambda o: self.ask_comment(True))
            act("attach_file", lambda o: self.pick_files_existing())
        if role != CLIENT and role != STAFF:
            act("order_history", self.show_history)

        # --- комментарии ---
        body.add_widget(Factory.Lbl(text=f"[b]{self.t('comments')}[/b]"))
        for c in d["comments"]:
            tag = "" if c["public"] else f" ({self.t('internal')})"
            body.add_widget(Factory.Lbl(text=f"[b]{e(c['author'])}[/b] {c['created_at'][:16].replace('T', ' ')}{tag}\n{e(c['text'])}"))
        # --- фото/видео ---
        body.add_widget(Factory.Lbl(text=f"[b]{self.t('media')}[/b]"))
        for m in d["media"]:
            url = self.api.media_url(m["id"])
            if m["mime"].startswith("image/"):
                body.add_widget(AsyncImage(source=url, size_hint_y=None, height=dp(220), fit_mode="contain"))
            else:  # видео открываем во внешнем плеере/браузере
                b = Factory.Row(text=f"video: {escape_markup(m['original'])}")
                b.bind(on_release=lambda *_a, u=url: webbrowser.open(u))
                body.add_widget(b)

    def post_order(self, action, body=None):
        self.api.post(f"/orders/{self.cur_order_id}/{action}", body, lambda r: self.load_order(), self.error)

    def change_status(self, o):
        self.pick(self.t("change_status"), [(self.status_label(s), s) for s in STATUSES],
                  lambda s: self.post_order("status", {"status": s}))

    def ask_estimate(self, o):
        def done(v):
            try:
                self.post_order("estimate", {"hours": float(v["hours"].replace(",", ".")),
                                             "price": float(v["price"].replace(",", ".")), "text": v["text"]})
            except ValueError:
                self.error("number?")
        self.form(self.t("estimate"), [("hours", "hours", False), ("price", "price", False),
                                       ("text", "estimate_text", False)], done)

    def ask_rating(self, o):
        self.pick(self.t("rate"), [("*" * i, i) for i in range(5, 0, -1)],
                  lambda r: self.post_order("rate", {"rating": r}))

    def ask_comment(self, public):
        self.form(self.t("message"), [("text", "text", False)],
                  lambda v: v["text"].strip() and self.post_order("comments", {"text": v["text"], "public": public}))

    def assign_executor(self, o):
        def got(users):
            ex = [u for u in users if u["role"] == EXECUTOR and u["is_active"]
                  and (not o["department_id"] or u["department_id"] == o["department_id"] or self.me["role"] == OWNER)]
            if not ex:
                return self.info(self.t("no_executors"))
            self.pick(self.t("assign_executor"), [(u["full_name"] or u["username"], u["id"]) for u in ex],
                      lambda uid: self.post_order("assign", {"executor_id": uid}))
        self.api.get("/users?role=3", got, self.error)

    def assign_department(self, o):
        self.api.get("/departments", lambda ds: self.pick(self.t("assign_dept"), [(d["name"], d["id"]) for d in ds],
                     lambda did: self.post_order("assign", {"department_id": did})), self.error)

    def show_history(self, o):
        def show(rows):
            self.info("\n".join(f"{r['created_at'][:16].replace('T', ' ')}  {r['actor']}: {r['action']} {r['details']}"
                                for r in rows) or self.t("no_data"), self.t("order_history"))
        self.api.get(f"/orders/{self.cur_order_id}/history", show, self.error)

    # ----- файлы (фото/видео) -----
    def choose_files(self, callback):
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=lambda sel: Clock.schedule_once(lambda dt: sel and callback(sel)),
                                  multiple=True)
        except Exception as ex:
            self.error(ex)

    def pick_files_existing(self):
        oid = self.cur_order_id
        self.choose_files(lambda files: self.upload_files(oid, list(files), self.load_order))

    def pick_files_new(self):
        self.choose_files(self.add_new_files)

    def add_new_files(self, files):
        self.new.setdefault("files", []).extend(files)
        self.update_summary()

    def upload_files(self, oid, files, done):
        """Загружаем файлы по одному, затем вызываем done()."""
        if not files:
            return done()
        path = files.pop(0)
        self.api.upload(f"/orders/{oid}/media", path, lambda r: self.upload_files(oid, files, done), self.error)

    # ----- создание заказа -----
    def load_order_new(self):
        self.new = {}
        sc = self.root.get_screen("order_new")
        for i in ("title", "descr", "address"):
            sc.ids[i].text = ""
        self.update_summary()

    def update_summary(self):
        n, parts = self.new, []
        if n.get("dep_name"):
            parts.append(f"{self.t('department')}: {n['dep_name']}")
        if n.get("client_name"):
            parts.append(f"{self.t('client')}: {n['client_name']}")
        if n.get("lat") is not None:
            parts.append(f"{self.t('location')}: {n['lat']:.5f}, {n['lon']:.5f}")
        if n.get("files"):
            parts.append(f"{self.t('files_attached')}{len(n['files'])}")
        self.root.get_screen("order_new").ids.summary.text = escape_markup("\n".join(parts))

    def pick_new_department(self):
        def chosen(d):
            self.new.update(department_id=d["id"], dep_name=d["name"])
            self.update_summary()
        self.api.get("/departments", lambda ds: self.pick(self.t("department"), [(d["name"], d) for d in ds], chosen), self.error)

    def pick_new_client(self):
        def chosen(u):
            self.new.update(client_id=u["id"], client_name=u["full_name"] or u["username"])
            self.update_summary()
        self.api.get("/users?role=4", lambda us: self.pick(self.t("client"), [(u["full_name"] or u["username"], u) for u in us], chosen), self.error)

    def use_gps(self, target="new"):
        self.loc_target = target
        try:
            from plyer import gps
            gps.configure(on_location=self._on_gps, on_status=lambda **k: None)
            gps.start(minTime=1000, minDistance=0)
            self.info(self.t("gps_wait"))
        except Exception:
            self.info(self.t("gps_unavailable"))

    def _on_gps(self, **kw):
        try:
            from plyer import gps
            gps.stop()
        except Exception:
            pass
        Clock.schedule_once(lambda dt: self.set_loc(self.loc_target, kw.get("lat"), kw.get("lon")))

    def set_loc(self, target, lat, lon):
        """Записать выбранное положение в черновик заказа ('new') или регистрации ('reg')."""
        if lat is None:
            return
        if target == "reg":
            self.reg.update(lat=lat, lon=lon)
            self.refresh_reg()
        else:
            self.new.update(lat=lat, lon=lon)
            self.update_summary()

    def submit_order(self, title, descr, address):
        if not title.strip():
            return self.error(self.t("title"))
        n = self.new
        body = dict(title=title, description=descr, address=address, lat=n.get("lat"), lon=n.get("lon"),
                    department_id=n.get("department_id"), client_id=n.get("client_id"))
        files = list(n.get("files", []))

        def created(o):
            self.upload_files(o["id"], files, lambda: (self.info(self.t("order_created")), self.go("orders")))
        self.api.post("/orders", body, created, self.error)

    # ----- карта -----
    def show_on_map(self, lat, lon):
        self.open_map("view", lat, lon)

    def pick_location(self):
        self.open_map("pick", self.new.get("lat") or 50.4501, self.new.get("lon") or 30.5234,
                      cb=lambda la, lo: self.set_loc("new", la, lo))  # по умолчанию Киев

    def open_map(self, mode, lat, lon, cb=None):
        self.map_ctx = dict(mode=mode, back=self.root.current, cb=cb)
        sc = self.root.get_screen("map")
        mv = sc.ids.mv
        for m in list(getattr(self, "_markers", [])):
            mv.remove_marker(m)
        self._markers = []
        sc.ids.cross.opacity = 1 if mode == "pick" else 0
        sc.ids.setbtn.disabled = mode != "pick"
        sc.ids.setbtn.opacity = 1 if mode == "pick" else 0
        if mode == "view":
            mk = MapMarker(lat=lat, lon=lon)
            mv.add_marker(mk)
            self._markers.append(mk)
        self.root.current = "map"

        def ready(src):
            self.apply_map_source(mv, src)
            # центрируем уже ПОСЛЕ того, как экран получил размер (иначе карта остаётся в точке 0,0)
            Clock.schedule_once(lambda dt: (setattr(mv, "zoom", 15), mv.center_on(lat, lon)), 0.2)
        self.ensure_map_source(ready)

    def map_back(self):
        self.root.current = self.map_ctx.get("back", "orders")

    def map_set(self):
        mv = self.root.get_screen("map").ids.mv
        cb = self.map_ctx.get("cb")
        if cb:
            cb(mv.lat, mv.lon)
        self.map_back()

    # ----- источники карт (см. maps.py) -----
    def fetch_map_config(self):
        """Берём с сервера, какой провайдер карт использовать (google/osm/custom/offline) и его ключи."""
        if not self.api.base:
            self.api.base = self.server_url
        self.api.get("/config", self._got_map_cfg, lambda e: None)

    def _got_map_cfg(self, cfg):
        self.map_cfg, self._map_src = cfg, None

    def ensure_map_source(self, cb):
        if self._map_src:
            return cb(self._map_src)
        provider = self.cfg.get("map_provider") or self.map_cfg.get("map_provider", "osm")
        cfg = dict(self.map_cfg, lang=self.lang, cache_root=self.user_data_dir)

        def done(src):
            self._map_src = src
            cb(src)
        build_source(provider, cfg, done)

    def apply_map_source(self, mv, src):
        mv.cache_dir = src.cache_dir
        mv.map_source = src

    def set_map_provider(self, code):
        self.cfg["map_provider"] = code or None
        self._map_src = None
        self.save_cfg()
        self.load_settings()

    # ----- камера и выбор документов -----
    def open_camera(self, cb):
        """Снимок документа камерой (макс. качество, см. camera.py). cb(список_путей)."""
        self.cam_cb, self.cam_back = cb, self.root.current
        if platform != "android":      # на ПК камеры нет — выбираем файл
            return self.choose_documents(cb)
        from android.permissions import Permission, check_permission, request_permissions
        if check_permission(Permission.CAMERA):
            self.root.current = "camera"
        else:
            def answered(perms, results):
                Clock.schedule_once(lambda dt: setattr(self.root, "current", "camera") if all(results)
                                    else self.error(self.t("camera_denied")))
            request_permissions([Permission.CAMERA], answered)

    def camera_done(self, path):
        self.root.current = self.cam_back
        if self.cam_cb:
            self.cam_cb([path])

    def camera_cancel(self):
        self.root.current = self.cam_back

    def choose_documents(self, cb):
        """Выбор JPEG/PDF из памяти устройства (тип дополнительно проверяет сервер по содержимому)."""
        try:
            from plyer import filechooser
            filechooser.open_file(filters=["*.jpg", "*.jpeg", "*.pdf"], multiple=True,
                                  on_selection=lambda sel: Clock.schedule_once(lambda dt: sel and cb(list(sel))))
        except Exception as ex:
            self.error(ex)

    def map_external(self):
        mv = self.root.get_screen("map").ids.mv
        webbrowser.open(f"https://www.openstreetmap.org/?mlat={mv.lat}&mlon={mv.lon}#map=17/{mv.lat}/{mv.lon}")

    # ----- пользователи -----
    def load_users(self):
        sc = self.root.get_screen("users")
        sc.title = self.t("users")
        sc.ids.actions.clear_widgets()
        if self.me["role"] in (OWNER, HEAD, CLIENT):
            b = Factory.Btn(text=self.t("add_user"))
            b.bind(on_release=lambda *_a: self.add_user())
            sc.ids.actions.add_widget(b)

        def show(users):
            def line(u):
                st = "" if u["is_active"] else f"  [{self.t('inactive')}]"
                return (f"[b]{escape_markup(u['full_name'] or u['username'])}[/b] (@{u['username']}){st}\n"
                        f"{self.t(ROLE_KEYS[u['role']])}")
            self.fill(sc.ids.list, [(line(u), (lambda u=u: self.manage_user(u))) for u in users])
        self.api.get("/users", show, self.error)

    def add_user(self):
        def got(v):
            body = dict(username=v["username"], password=v["password"], full_name=v["full_name"], phone=v["phone"])
            if self.me["role"] == OWNER:   # владелец выбирает роль нового пользователя
                self.pick(self.t("role"), [(self.t(k), r) for r, k in ROLE_KEYS.items()],
                          lambda r: self.api.post("/users", dict(body, role=r), lambda _r: self.load_users(), self.error))
            else:                          # роль начальник/заказчик сервер назначает сам
                self.api.post("/users", body, lambda _r: self.load_users(), self.error)
        self.form(self.t("add_user"), [("username", "username", False), ("password", "password", True),
                                       ("full_name", "full_name", False), ("phone", "phone", False)], got)

    def manage_user(self, u):
        me, opts = self.me, []
        if me["role"] == OWNER:
            opts = [(self.t("change_role"), "role"), (self.t("change_department"), "dep"), (self.t("toggle_active"), "act")]
        elif me["role"] == HEAD and u["role"] == EXECUTOR:
            dep = None if u["department_id"] == me["department_id"] else me["department_id"]
            opts = [(self.t("change_department"), ("head_dep", dep))]
        if not opts:
            return
        self.pick(u["username"], opts, lambda a: self.user_action(u, a))

    def user_action(self, u, a):
        def patch(body):
            self.api.patch(f"/users/{u['id']}", body, lambda _r: self.load_users(), self.error)
        if a == "role":
            self.pick(self.t("role"), [(self.t(k), r) for r, k in ROLE_KEYS.items()], lambda r: patch({"role": r}))
        elif a == "dep":
            self.api.get("/departments", lambda ds: self.pick(self.t("department"),
                         [(self.t("none"), None)] + [(d["name"], d["id"]) for d in ds], lambda d: patch({"department_id": d})), self.error)
        elif a == "act":
            patch({"is_active": not u["is_active"]})
        elif isinstance(a, tuple):
            patch({"department_id": a[1]})

    # ----- направления (владелец) -----
    def load_departments(self):
        sc = self.root.get_screen("departments")
        sc.title = self.t("departments")
        sc.ids.actions.clear_widgets()
        b = Factory.Btn(text=self.t("add_department"))
        b.bind(on_release=lambda *_a: self.form(self.t("add_department"), [("name", "name", False)],
               lambda v: self.api.post("/departments", {"name": v["name"]}, lambda _r: self.load_departments(), self.error)))
        sc.ids.actions.add_widget(b)
        self.api.get("/departments", lambda ds: self.fill(sc.ids.list, [
            (f"[b]{escape_markup(d['name'])}[/b]\n{self.t('head')}: {escape_markup(d['head_name'] or '-')}",
             lambda d=d: self.set_head(d)) for d in ds]), self.error)

    def set_head(self, d):
        """Назначить начальника направления: он получит роль 2 (пользователь выбирается из списка)."""
        def got(users):
            self.pick(self.t("set_head"), [(u["full_name"] or u["username"], u["id"]) for u in users if u["is_active"]],
                      lambda uid: self.api.patch(f"/departments/{d['id']}", {"head_id": uid},
                                                 lambda _r: self.load_departments(), self.error))
        self.api.get("/users", got, self.error)

    # ----- журнал (владелец) -----
    def load_audit(self):
        sc = self.root.get_screen("audit")
        sc.title = self.t("history")
        sc.ids.actions.clear_widgets()
        self.api.get("/audit", lambda rows: self.fill(sc.ids.list, [
            (f"{r['created_at'][:16].replace('T', ' ')}  [b]{escape_markup(r['actor'])}[/b]\n"
             f"{r['action']} → {r['target_type']} #{r['target_id']} {escape_markup(r['details'])}", None) for r in rows]), self.error)

    # ----- настройки -----
    def load_settings(self):
        sc = self.root.get_screen("settings")
        sc.title = self.t("settings")
        sc.ids.actions.clear_widgets()
        m = self.me
        self.fill(sc.ids.list, [
            (f"[b]{self.t('profile')}[/b]\n{escape_markup(m['full_name'] or m['username'])} — {self.t(ROLE_KEYS[m['role']])}", None),
            (self.t("language"), self.pick_language),
            (f"{self.t('map_provider')}: {self.t('mp_' + self.cfg['map_provider']) if self.cfg.get('map_provider') else self.t('mp_server')}",
             lambda: self.pick(self.t("map_provider"), [(self.t("mp_server"), None), (self.t("mp_google"), "google"),
                               (self.t("mp_osm"), "osm"), (self.t("mp_custom"), "custom"),
                               (self.t("mp_offline"), "offline")], self.set_map_provider)),
            (self.t("take_photo"), lambda: self.open_camera(lambda f: self.upload_my_docs(list(f), lambda: self.info(self.t("uploaded"))))),
            (self.t("choose_document"), lambda: self.choose_documents(lambda f: self.upload_my_docs(list(f), lambda: self.info(self.t("uploaded"))))),
            (self.t("logout"), self.logout),
        ])


def Widget_():
    from kivy.uix.widget import Widget
    return Widget()


if __name__ == "__main__":
    ServiceApp().run()
