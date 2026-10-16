"""
Съёмка документа камерой устройства в МАКСИМАЛЬНОМ качестве (Android, CameraX через Camera4Kivy).
Настройки качества — в методе on_enter:
  optimize='quality'            режим CameraX «максимальное качество» (вместо «минимальная задержка»)
  sensor_resolution=(4000,3000) просим наибольшее разрешение; CameraX подберёт ближайшее поддерживаемое
  автофокус по касанию, зум щипком, вспышка auto/on/off
Фото сохраняется в ПРИВАТНОЙ папке приложения (не попадает в галерею) как JPEG.
Вне Android (отладка на ПК) показывается заглушка.
"""
import time

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.utils import platform

MAX_RESOLUTION = (4000, 3000)   # 12 Мп; для 48 Мп датчиков можно увеличить


class CameraScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="camera", **kw)
        self.app = app
        self.preview = None
        root = FloatLayout()
        if platform == "android":
            from camera4kivy import Preview
            self.preview = Preview(aspect_ratio="4:3")
            root.add_widget(self.preview)
        else:
            root.add_widget(Label(text="[camera preview — Android only]", color=(.6, .6, .6, 1)))
        self.hint = Label(size_hint=(1, None), height=dp(40), pos_hint={"x": 0, "top": 1},
                          color=(1, 1, 1, 1), text_size=(dp(340), None), halign="center")
        root.add_widget(self.hint)
        bar = BoxLayout(size_hint=(1, None), height=dp(84), pos_hint={"x": 0, "y": 0}, padding=dp(8), spacing=dp(8))
        self.btn_back, self.btn_shoot, self.btn_flash = Button(), Button(font_size="20sp", bold=True), Button()
        self.btn_back.bind(on_release=lambda *_: app.camera_cancel())
        self.btn_shoot.bind(on_release=lambda *_: self.shoot())
        self.btn_flash.bind(on_release=lambda *_: self.toggle_flash())
        for b in (self.btn_back, self.btn_shoot, self.btn_flash):
            bar.add_widget(b)
        root.add_widget(bar)
        self.add_widget(root)

    def on_pre_enter(self, *a):
        t = self.app.t
        self.hint.text, self.btn_back.text, self.btn_shoot.text, self.btn_flash.text = \
            t("camera_hint"), t("back"), t("shoot"), t("flash")

    def on_enter(self, *a):
        if self.preview:
            self.preview.connect_camera(camera_id="back", optimize="quality", sensor_resolution=MAX_RESOLUTION,
                                        default_flash="auto", default_zoom=0.0, enable_video=False,
                                        enable_zoom_gesture=True, enable_focus_gesture=True,
                                        filepath_callback=self.on_saved)

    def on_leave(self, *a):
        if self.preview:
            self.preview.disconnect_camera()

    def shoot(self):
        if self.preview:
            self.preview.capture_photo(location="private", subdir="docs", name="doc_" + time.strftime("%Y%m%d_%H%M%S"))

    def toggle_flash(self):
        if self.preview:
            self.preview.flash()

    def on_saved(self, path):   # вызывается Camera4Kivy после сохранения снимка
        Clock.schedule_once(lambda dt: self.app.camera_done(path))
