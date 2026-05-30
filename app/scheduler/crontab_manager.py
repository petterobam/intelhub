"""Crontab Manager - 系统级定时任务管理

在 macOS/Linux 系统 crontab 中安装/卸载任务，
让任务在 Flask APP 关闭时也能继续执行。

用法:
  CrontabManager.install(task_id, task_name, schedule_expr, script_path)
  CrontabManager.uninstall(task_id)
  CrontabManager.list()  -> [task_id, ...]
  CrontabManager.install_all_from_db(db_path, base_dir)
  CrontabManager.is_installed(task_id) -> bool
"""
import subprocess
import datetime
import os

MARKER_START = "# === IntelHub Task Start"
MARKER_END   = "# === IntelHub Task End"


def _current_crontab() -> str:
    try:
        r = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return r.stdout
        return ""
    except Exception:
        return ""


def _parse_crontab_line(line: str) -> tuple:
    """返回 (task_id, is_intelhub)"""
    if not line.startswith('# intelhub:'):
        return None, False
    parts = line.strip().split(None, 1)
    if len(parts) < 2:
        return None, False
    return parts[1], True


def _lines_for_task(base_dir: str, task_id: str, task_name: str,
                    schedule_expr: str, script_path: str) -> list:
    """生成 crontab 条目（包含标记行）"""
    python_bin = os.popen('which python3').read().strip() or 'python3'
    marker_comment = f"# intelhub: {task_id}  # {task_name}"
    cmd = f'cd {base_dir} && {python_bin} run.py task run {task_id} >> {base_dir}/.logs/cron_{task_id}.log 2>&1'
    return [marker_comment, f"{schedule_expr} {cmd}"]


class CrontabManager:
    """管理 IntelHub 任务在系统 crontab 中的安装状态"""

    @staticmethod
    def install(base_dir: str, task_id: str, task_name: str,
               schedule_expr: str, script_path: str = '') -> dict:
        """
        安装任务到系统 crontab。
        schedule_expr: 标准 cron 表达式，如 "0 9 * * 1-5" (工作日9点)
        """
        CrontabManager.uninstall(task_id)  # 先移除旧的

        base_dir = os.path.abspath(base_dir)
        lines = _lines_for_task(base_dir, task_id, task_name, schedule_expr, script_path)

        current = _current_crontab()
        crontab_lines = current.splitlines() if current else []

        # 移除已存在的该 task 的条目（通过标记注释）
        new_lines = []
        skip = False
        for line in crontab_lines:
            if f'# intelhub: {task_id}' in line:
                skip = True
                continue
            if skip and line.startswith('# === IntelHub'):
                skip = False
                continue
            if not skip:
                new_lines.append(line)

        # 添加新条目
        new_lines.extend([MARKER_START, *lines, MARKER_END])

        new_crontab = '\n'.join(new_lines).strip() + '\n'
        try:
            r = subprocess.run(
                ['crontab', '-'],
                input=new_crontab.encode() if hasattr(subprocess, 'run') and hasattr(r, 'communicate') else new_crontab,
                timeout=10
            )
            # 用 echo 管道方式更可靠
            p = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate(new_crontab.encode('utf-8'), timeout=10)
            if p.returncode == 0:
                return {'status': 'installed', 'task_id': task_id, 'cron': schedule_expr}
            return {'status': 'error', 'message': stderr.decode()[:200]}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def uninstall(task_id: str) -> dict:
        """从系统 crontab 移除任务"""
        current = _current_crontab()
        if not current:
            return {'status': 'not_found', 'task_id': task_id}

        crontab_lines = current.splitlines()
        new_lines = []
        skip = False
        for line in crontab_lines:
            if f'# intelhub: {task_id}' in line:
                skip = True
                continue
            if skip and line.startswith('# === IntelHub'):
                skip = False
                continue
            if not skip:
                new_lines.append(line)

        new_crontab = '\n'.join(new_lines).strip() + '\n'
        try:
            p = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate(new_crontab.encode('utf-8'), timeout=10)
            return {'status': 'uninstalled', 'task_id': task_id}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def is_installed(task_id: str) -> bool:
        """检查任务是否已安装到 crontab"""
        current = _current_crontab()
        return f'# intelhub: {task_id}' in current

    @staticmethod
    def list_installed() -> list:
        """列出所有已安装的任务ID"""
        current = _current_crontab()
        result = []
        for line in current.splitlines():
            if line.startswith('# intelhub:'):
                parts = line.strip().split(None, 1)
                if len(parts) >= 1:
                    result.append(parts[1])
        return result

    @staticmethod
    def install_all_from_db(db_path: str, base_dir: str) -> dict:
        """从数据库读取所有启用任务，安装到 crontab"""
        import sqlite3, json
        base_dir = os.path.abspath(base_dir)
        try:
            conn = sqlite3.connect(db_path)
            tasks = conn.execute(
                "SELECT id, name, enabled, schedule_type, schedule_config FROM scheduled_tasks"
            ).fetchall()
            conn.close()

            installed = []
            for task_id, name, enabled, sched_type, sched_cfg in tasks:
                if not enabled:
                    continue
                cfg = json.loads(sched_cfg or '{}')
                # 转换为 cron 表达式
                if sched_type == 'cron':
                    cron_expr = _db_cfg_to_cron(cfg)
                elif sched_type == 'interval':
                    cron_expr = _interval_to_cron(cfg)
                else:
                    continue

                if cron_expr:
                    result = CrontabManager.install(base_dir, task_id, name, cron_expr)
                    if result['status'] == 'installed':
                        installed.append(task_id)

            return {'status': 'done', 'installed': len(installed), 'tasks': installed}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


def _db_cfg_to_cron(cfg: dict) -> str:
    """将 DB 中的 cron 配置 dict 转换为 cron 表达式"""
    hour = cfg.get('hour', '*')
    minute = cfg.get('minute', '0')
    day = cfg.get('day_of_week', '*')
    month = cfg.get('month', '*')
    dom = cfg.get('day', '*')

    if isinstance(hour, list):
        # 多个小时：生成多条（简化处理，取第一个）
        h = hour[0] if hour else '*'
    else:
        h = hour

    h_str = str(h) if h != '*' else '*'
    m_str = str(minute).zfill(2) if minute != '*' else '0'
    return f"{m_str} {h_str} {dom} {month} {day}"


def _interval_to_cron(cfg: dict) -> str:
    """将 interval 配置转换为 @hourly/@daily 或简单 cron"""
    mins = cfg.get('minutes', 60)
    if mins % 60 == 0:
        hrs = mins // 60
        if hrs == 1:
            return '0 * * * *'  # 每小时
        elif hrs == 24:
            return '0 9 * * *'  # 每天9点
        else:
            return f'0 */{hrs} * * *'  # 每N小时
    elif mins < 60:
        # 每N分钟：crontab 最小粒度是分钟，用 @hourly 近似
        return f'*/{mins} * * * *'
    return None
