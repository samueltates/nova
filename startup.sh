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
export LIBGL_PATH=/nix/store/$(ls -1 /nix/store | grep 'libglvnd-' | awk '!/-lib$|\.drv$|-bin$|\.tar.xz.drv$/')
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$LIBGL_PATH/lib
export GLIB_PATH=/nix/store/$(ls -1 /nix/store | grep 'glib-' | awk '!/-lib$|\.drv$|-bin$|\.tar.xz.drv$/')
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$GLIB_PATH/lib
export GLIB_THREAD_PATH=$(find /nix/store -name libgthread-2.0.so.0 | head -n1 | xargs dirname)
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$GLIB_THREAD_PATH
Find the directory containing libcublas.so
export CUBLAS_PATH_DIR=$(find / -name libcublas.so | grep -m 1 libcublas | xargs dirname)
echo $CUBLAS_PATH_DIR
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CUBLAS_PATH_DIR

# Find the directory containing libcufft.so
export CUFFT_PATH_DIR=$(find / -name libcufft.so | grep -m 1 libcufft | xargs dirname)
echo $CUFFT_PATH_DIR
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CUFFT_PATH_DIR

export LD_LIBRARY_PATH

# Export the updated LD_LIBRARY_PATH
export LD_LIBRARY_PATH
echo $LD_LIBRARY_PATH
# echo $FONTCONFIG_PATH
# echo $FONTCONFIG_FILE
# echo $GOOGLE_FONT_PATH
# echo $MAGIC_FONT_PATH
# echo $(fc-list)
# echo $(convert -list font)

pipenv run python main.py
