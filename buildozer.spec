[app]

title = Home Master
package.name = homemaster
package.domain = org.homemaster
source.dir = .
source.include_exts = py,kv,json,png,jpg,java
source.exclude_dirs = tools,bin,.buildozer,.github
version = 1.0

# Все необходимые плагины и библиотеки
requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,plyer,pyjnius,android,camera4kivy,gestures4kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,CAMERA,READ_EXTERNAL_STORAGE

icon.filename = %(source.dir)s/icon.png

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
