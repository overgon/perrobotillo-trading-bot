#!/bin/bash
# Honeygain startup script
export LD_LIBRARY_PATH="/home/overgon/.openclaw/workspace:$LD_LIBRARY_PATH"
cd "/home/overgon/.openclaw/workspace"
exec ./honeygain -tou-accept \
  -email "$HONEYGAIN_EMAIL" \
  -pass "$HONEYGAIN_PASS" \
  -device "myPi5-b"
