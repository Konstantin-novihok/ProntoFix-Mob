#!/usr/bin/env bash
# Local build on Ubuntu 22.04 / WSL2. First build downloads Android SDK/NDK.
set -euo pipefail

sudo apt-get update
sudo apt-get install -y \
  git zip unzip openjdk-17-jdk python3-pip python3-venv \
  autoconf automake libtool pkg-config zlib1g-dev \
  libncurses5-dev libncursesw5-dev libtinfo5 cmake \
  libffi-dev libssl-dev build-essential ccache

# Force the local build to use JDK 17 rather than a preinstalled Java 11.
if [[ -d /usr/lib/jvm/java-17-openjdk-amd64 ]]; then
  export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
  export PATH="$JAVA_HOME/bin:$PATH"
else
  echo "ERROR: JDK 17 not found. Install openjdk-17-jdk and retry." >&2
  exit 1
fi

java -version
javac -version

python3 -m venv .bzenv
source .bzenv/bin/activate
python -m pip install --upgrade pip
python -m pip install buildozer==1.5.0 cython==0.29.37
buildozer -v android debug 2>&1 | tee build.log
cp bin/*.apk HomeMaster.apk
echo "Done: HomeMaster.apk"
