#!/bin/bash
redis-server &
REDIS_PID=$!
pipenv run python main.py
kill $REDIS_PID