#!/usr/bin/env bash
# Локальная сборка на Ubuntu 22.04 / WSL2 (первая сборка 30-60 минут, нужно ~10 ГБ места).
set -e
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv autoconf automake libtool \
  pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev build-essential ccache
python3 -m venv .bzenv && . .bzenv/bin/activate
pip install buildozer==1.5.0 cython==0.29.37
buildozer -v android debug 2>&1 | tee build.log
cp bin/*.apk HomeMaster.apk && echo "Готово: HomeMaster.apk"
