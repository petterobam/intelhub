"""Gunicorn config — assign scheduler roles to specific workers.

Layout (workers=3):
  Worker-0: pure web (no scheduler)
  Worker-1: system scheduler (system tasks)
  Worker-2: user scheduler (user tasks)
  Worker-3+: user scheduler (future, user_id hash distribution)

When NOT running under gunicorn (e.g. python run.py server),
INTElHUB_SCHEDULER_ROLE defaults to "system" — loads all tasks.
"""

import os

# 进程名标识 — ps/top 中显示为 intelhub: master / intelhub: worker
proc_name = "intelhub"


def on_starting(server):
    # Use a file-based counter shared across forks
    _counter_file = '/tmp/intelhub_worker_counter'
    with open(_counter_file, 'w') as f:
        f.write('0')


def post_fork(server, worker):
    # Atomically increment counter to get unique worker index
    _counter_file = '/tmp/intelhub_worker_counter'
    try:
        with open(_counter_file, 'r+') as f:
            idx = int(f.read().strip() or '0')
            f.seek(0)
            f.write(str(idx + 1))
            f.truncate()
    except Exception:
        idx = 0

    if idx == 0:
        os.environ["INTElHUB_SCHEDULER_ROLE"] = "none"
    elif idx == 1:
        os.environ["INTElHUB_SCHEDULER_ROLE"] = "system"
    else:
        os.environ["INTElHUB_SCHEDULER_ROLE"] = "user"

    os.environ["INTElHUB_WORKER_ID"] = str(idx)
