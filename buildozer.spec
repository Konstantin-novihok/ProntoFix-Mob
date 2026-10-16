[app]
title = Home Master
package.name = homemaster
package.domain = org.homemaster
source.dir = .
source.include_exts = py,kv,json,png,jpg,java
source.exclude_dirs = tools,bin,.buildozer,.github
version = 1.0

# Зависимости (python-for-android соберёт их в APK)
requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,plyer,pyjnius,android,kivy-garden.mapview,camera4kivy,gestures4kivy

orientation = portrait
fullscreen = 0

# Права: интернет, GPS, камера/файлы (фото и видео)
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,CAMERA,READ_EXTERNAL_STORAGE

# Совместимость: Android 5.0 = API 21
android.minapi = 21
android.api = 33
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
# Закреплённая проверенная версия python-for-android (Kivy 2.3.0, NDK 25b, API 33, minapi 21)
p4a.branch = v2024.01.21

# Camera4Kivy: подключает CameraX (папка camerax_provider лежит в проекте)
p4a.hook = camerax_provider/gradle_options.py

[buildozer]
log_level = 2
warn_on_root = 0
