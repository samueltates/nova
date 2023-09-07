#!/bin/bash
redis-cli flushall &
redis-server &
REDIS_PID=$!
export FONTCONFIG_FILE=/etc/fonts/fonts.conf
export XDG_CONFIG_HOME=$XDG_CONFIG_HOME/fontconfig
convert -version
pipenv run python main.py