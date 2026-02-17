#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import sys

result = subprocess.run(
    [sys.executable, 'test_fastembed_monitor.py'],
    capture_output=True,
    text=True,
    cwd=r'D:\MoneyProjects\qmd-python'
)

# 过滤 onnxruntime 警告
lines = result.stdout.split('\n')
filtered = [l for l in lines if 'onnxruntime' not in l and 'W:onnxruntim' not in l]

print('\n'.join(filtered))
