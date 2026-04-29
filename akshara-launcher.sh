#!/bin/bash
# AKSHARA launcher - uses conda environment
export PATH="/home/detour/anaconda3/bin:$PATH"
cd /home/detour/Documents/akshara
exec /home/detour/anaconda3/bin/conda run -n akshara --no-capture-output python main.py "$@"
