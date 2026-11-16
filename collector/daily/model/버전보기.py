# -*- coding: utf-8 -*-
"""이 컴퓨터의 파이썬·패키지 버전을 보여 주고 버전_이PC.txt 로 저장"""
import importlib, platform, sys, os
rows = [('python', sys.version.split()[0]), ('OS', platform.platform())]
for m in ('pandas', 'numpy', 'lightgbm', 'sklearn', 'scipy', 'pypdf', 'lxml'):
    try:
        rows.append((m, importlib.import_module(m).__version__))
    except Exception as e:
        rows.append((m, f'없음 ({type(e).__name__})'))
txt = '\n'.join(f'{k:<10} {v}' for k, v in rows)
print(txt)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '버전_이PC.txt'), 'w', encoding='utf-8').write(txt + '\n')
