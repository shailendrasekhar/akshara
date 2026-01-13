#!/bin/bash
# AKSHARA launcher - uses conda environment
export PATH="/home/detour/anaconda3/bin:$PATH"
cd /home/detour/Documents/SideProjects/Talk2me
exec /home/detour/anaconda3/bin/conda run -n talk2me --no-capture-output python main.py "$@"
