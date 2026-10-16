"""
Локализация. Все тексты лежат в locales/<код>.json.
ЧТОБЫ ДОБАВИТЬ ЯЗЫК: скопируйте locales/en.json в locales/de.json, переведите значения,
поле "_name" — название языка в списке. Больше ничего менять не нужно: язык появится в меню сам.
"""
import json
import os


class I18n:
    def __init__(self, folder, default="en"):
        self.default = default
        self.data = {}
        for fn in sorted(os.listdir(folder)):
            if fn.endswith(".json"):
                with open(os.path.join(folder, fn), encoding="utf-8") as f:
                    self.data[fn[:-5]] = json.load(f)

    def languages(self):
        """[(код, название)] для меню выбора языка."""
        return [(c, d.get("_name", c)) for c, d in self.data.items()]

    def t(self, key, lang):
        """Перевод; если ключа нет в языке — берём английский, затем сам ключ."""
        return self.data.get(lang, {}).get(key) or self.data.get(self.default, {}).get(key) or key
