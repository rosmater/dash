#!/usr/bin/env python3
"""t6285u: общий безопасный пуш для скриптов-синков даша (sync_dash_taps, queue_autoclear, …).
Репо = /workspace/dash-gh (копировать некуда). Коммитим ТОЛЬКО переданные файлы + собранные выходы, без `git add -A`;
push не прошёл → pull --rebase --autostash, пересборка, снова (3 попытки). Без --force / --no-verify."""
import os, subprocess
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = ['index.html', 'helper.html', 'assistant.html', 'variant-a.html', 'variant-b.html', 'variant-c.html',
           'data.enc.json', 'data-asst.enc.json', 'data-test-ma.enc.json', 'test-messengers-assistants.html']

def git(*a):
    return subprocess.run(['git', '-C', R, *a], capture_output=True, text=True)

def push_with_retry(files, msg, tries=3, build=True):
    for n in range(tries):
        if git('pull', '-q', '--rebase', '--autostash', '-X', 'theirs', 'origin', 'main').returncode:
            git('rebase', '--abort'); print('pull fail, try', n + 1); continue
        if build and (subprocess.run(['bash', f'{R}/src/build_test_ma.sh']).returncode or subprocess.run(['bash', f'{R}/src/build.sh']).returncode):
            print('build fail, try', n + 1); continue
        add = [f for f in list(files) + (OUTPUTS if build else []) if os.path.exists(f'{R}/{f}')]
        if add: git('add', '--', *add)
        if git('diff', '--cached', '--quiet').returncode:
            git('-c', 'user.name=rosmater', '-c', 'user.email=rost@rosmater.local', 'commit', '-qm', msg)
        if not git('rev-list', '-1', 'origin/main..HEAD').stdout.strip():
            print('nothing to push'); return True
        r = git('push', '-q', 'origin', 'HEAD:main')
        if r.returncode == 0: print('pushed'); return True
        print('push fail, try', n + 1, r.stderr[-300:])
    return False
