#!/usr/bin/env python3
"""Rost t5996u guard: падает (exit 1), если мейн/родительская CU-задача попала в данные даша.
  python3 src/guard_parents.py            # data.json (после build_data.py)
  python3 src/guard_parents.py --enc      # + расшифровать data.enc.json и data-asst.enc.json (после cu_due_sync)"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cu_parents
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
bad = []
D = json.load(open(os.path.join(ROOT, 'data.json')))
bad += [('data.json',) + x for x in cu_parents.found(D)]
if '--enc' in sys.argv:
    import cu_due_sync as C
    for f, v in (('data.enc.json', C.VAULT_MAIN), ('data-asst.enc.json', C.VAULT_ASST)):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            d = C.decrypt(C.Path(p), v)[0]
            bad += [(f,) + x for x in cu_parents.found(d)]
if bad:
    for b in bad[:40]: print('PARENT ON DASH', *b)
    sys.exit(1)
print('guard_parents ok')
