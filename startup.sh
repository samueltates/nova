#!/bin/bash
redis-cli flushall &
redis-server &
REDIS_PID=$!
convert -version

echo $FONTCONFIG_PATH
echo $FONTCONFIG_FILE
export FONTCONFIG_PATH=/nix/store/$(ls -1 /nix/store | grep 'fontconfig-' | awk '!/-lib$|\.drv$|-bin$|\.tar.xz.drv$/')
export FONTCONFIG_FILE="$FONTCONFIG_PATH/etc/fonts/fonts.conf"
export IMAGE_MAGICK_PATH=/nix/store/$(ls -1 /nix/store | grep 'imagemagick-' | awk '!/-lib$|\.drv$|-bin$|\.tar.xz.drv$/')
export IMAGE_MAGICK_POLICY_PATH="$IMAGE_MAGICK_PATH"/etc/ImageMagick-7/policy.xml
export GOOGLE_FONT_PATH=/nix/store/$(ls -1 /nix/store | grep 'google-fonts-' | awk '!/-lib$|\.drv$|-bin$|\.tar.xz.drv$/')/etc/fonts
export MAGIC_FONT_PATH=/app/fonts/Oswald/static/Oswald-Bold.ttf
# echo $FONTCONFIG_PATH
# echo $FONTCONFIG_FILE
# echo $GOOGLE_FONT_PATH
# echo $MAGIC_FONT_PATH
# echo $(fc-list)
# echo $(convert -list font)

pipenv run python main.py
