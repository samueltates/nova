#!/bin/bash
convert -version
redis-cli flushall &
redis-server &
REDIS_PID=$!
pipenv run python main.py