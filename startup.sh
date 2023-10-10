#!/bin/bash
redis-cli flushall &
redis-server &
REDIS_PID=$!
convert -version

echo $FONTCONFIG_PATH
echo $FONTCONFIG_FILE
export FONTCONFIG_PATH=/nix/store/$(ls -1 /nix/store | grep 'fontconfig-' | awk '!/-lib$|\.drv$|-bin$|\.tar.xz.drv$/')
export FONTCONFIG_FILE="$FONTCONFIG_PATH/etc/fonts/fonts.conf"
echo $FONTCONFIG_PATH
echo $FONTCONFIG_FILE
echo $(fc-list)

pipenv run python main.py
