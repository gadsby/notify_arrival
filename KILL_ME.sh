#!/usr/bin/env bash

PID=$(ps -ef | grep "notify_arrival.py" | grep -v "grep" | awk '{print $2}')
kill -9 $PID