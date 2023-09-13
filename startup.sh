#!/bin/bash
redis-cli flushall &
redis-server &
REDIS_PID=$!
convert -version
pipenv run python main.py
