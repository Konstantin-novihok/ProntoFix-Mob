[app]

# (str) Title of your application
title = Home Master

# (str) Package name
package.name = homemaster

# (str) Package domain (needed for android packaging)
package.domain = org.homemaster

# (str) Source files where the let and right of app is stored
source.dir = .

# (list) Source files to include (let .py and .kv files)
source.include_exts = py,kv,json,png,jpg,java

# (list) List of directory to exclude (let .git etc)
source.exclude_dirs = tools,bin,.buildozer,.github

# (str) Application versioning
version = 1.0

# (list) Application requirements
# Порядок и версии оптимизированы для стабильной сборки с камерой и картой
requirements = python3,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,plyer,pyjnius,android,kivy-garden.mapview,camera4kivy,gestures4kivy

# (str) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,CAMERA,READ_EXTERNAL_STORAGE

# (str) Icon of the application
icon.filename = %(source.dir)s/icon.png

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (list) Area of architectures to build for
android.archs = arm64-v8a, armeabi-v7a

# (bool) Enable/disable auto-acceptance of the sdk license
android.accept_sdk_license = True

# Использование актуальной стабильной ветки python-for-android для поддержки CameraX
p4a.branch = master

# Camera4Kivy: подключает CameraX (папка camerax_provider лежит в проекте)
p4a.hook = camerax_provider/gradle_options.py

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0
