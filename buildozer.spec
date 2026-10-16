[app]
title = Home Master
package.name = homemaster
package.domain = org.homemaster
source.dir = .
source.include_exts = py,kv,json,png,jpg,java
source.exclude_dirs = tools,bin,.buildozer,.github
version = 1.0

requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,plyer,pyjnius,android,camera4kivy,gestures4kivy

orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,CAMERA,READ_EXTERNAL_STORAGE
icon.filename = %(source.dir)s/icon.pngname: Build Android APK

on:
  push:
    branches: [ main, master ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies & Buildozer
        run: |
          sudo apt-get update
          sudo apt-get install -y \
              git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
              zlib1g-dev libncurses5-dev cmake libffi-dev libssl-dev
          pip install --upgrade pip
          pip install --upgrade buildozer cython==0.29.33 setuptools

      - name: Clean old buildozer cache
        run: |
          rm -rf .buildozer

      - name: Build APK with Buildozer
        env:
          ANDROID_NDK_ROOT: /home/runner/.buildozer/android/platform/android-ndk-r25b
          ANDROID_NDK: /home/runner/.buildozer/android/platform/android-ndk-r25b
          ANDROID_NDK_HOME: /home/runner/.buildozer/android/platform/android-ndk-r25b
        run: |
          buildozer -v android debug

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: HomeMaster APK
          path: bin/*.apk

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

# Используем master, так как она поддерживает актуальные компиляторы
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 0
