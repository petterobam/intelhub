"""Task Executor - 统一执行器，支持 5 种任务类型

task_type:
  script    - Shell 脚本 (cron_wrapper)
  analysis  - LLM 分析 (Agent)
  crawler   - 爬虫任务 (Runner)
  knowledge - 知识库任务 (KB Manager)
  report    - 报告生成器
"""
import subprocess
import threading
import logging
import os
import datetime
from app.utils.helpers import bj_now
import json
import importlib
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TaskExecutor:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.active_tasks = {}

    def execute(self, task) -> dict:
        task_id = task.id
        start_time = bj_now()
        self.active_tasks[task_id] = {'start_time': start_time, 'status': 'running'}

        try:
            task_type = getattr(task, 'task_type', 'script')
            handler = {
                'script': self._execute_script,
                'analysis': self._execute_analysis,
                'crawler': self._execute_crawler,
                'knowledge': self._execute_knowledge,
                'report': self._execute_report,
            }.get(task_type, self._execute_script)

            result = handler(task)

            end_time = bj_now()
            duration = (end_time - start_time).total_seconds()

            outcome = {
                'task_id': task_id,
                'status': result.get('status', 'success' if result.get('exit_code', 0) == 0 else 'failed'),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': round(duration, 1),
                'stdout': result.get('stdout', '')[-10000:],
                'stderr': result.get('stderr', '')[-3000:],
                'exit_code': result.get('exit_code', 0),
                'artifacts': result.get('artifacts', []),
            }
            self.active_tasks[task_id] = outcome
            return outcome
        except subprocess.TimeoutExpired:
            return {'task_id': task_id, 'status': 'timeout', 'error': 'Execution timed out (10 min)'}
        except Exception as e:
            logger.error("Task %s execution failed: %s", task_id, e)
            return {'task_id': task_id, 'status': 'error', 'error': str(e)}

    # ------------------------------------------------------------------
    # script: Shell 脚本
    # ------------------------------------------------------------------
    def _execute_script(self, task) -> dict:
        script_path = os.path.join(self.base_dir, 'scripts', 'cron_wrappers', task.script)
        if not os.path.exists(script_path):
            return {
                'status': 'error',
                'stdout': '',
                'stderr': f'Script not found: {script_path}',
                'exit_code': 1,
            }

        result = subprocess.run(
            ['bash', script_path],
            capture_output=True, text=True, timeout=600,
            cwd=self.base_dir,
        )

        artifacts = self._scan_artifacts(task)

        return {
            'status': 'success' if result.returncode == 0 else 'failed',
            'stdout': result.stdout,
            'stderr': result.stderr,
            'exit_code': result.returncode,
            'artifacts': artifacts,
        }

    # ------------------------------------------------------------------
    # analysis: LLM Agent
    # ------------------------------------------------------------------
    def _execute_analysis(self, task) -> dict:
        try:
            script_name = getattr(task, 'script', '') or ''

            # 如果有对应 wrapper 脚本，优先用它
            wrapper = os.path.join(self.base_dir, 'scripts', 'cron_wrappers', script_name)
            if os.path.exists(wrapper):
                return self._execute_script(task)

            # 否则直接调用 Agent
            analysis_map = {
                'heartbeat': 'analysis.agents:HeartbeatAgent',
                'insight': 'analysis.agents:InsightAgent',
                'optimization': 'analysis.agents:OptimizationAgent',
            }

            agent_key = 'heartbeat'
            for key in analysis_map:
                if key in script_name.lower():
                    agent_key = key
                    break

            module_path, class_name = analysis_map[agent_key].split(':')
            mod = importlib.import_module(module_path)
            agent_cls = getattr(mod, class_name)
            agent = agent_cls()
            result = agent.run()

            artifacts = self._scan_artifacts(task)

            return {
                'status': result.get('status', 'unknown'),
                'stdout': json.dumps(result, ensure_ascii=False, indent=2)[:5000],
                'stderr': '',
                'exit_code': 0 if result.get('status') in ('success', 'offline') else 1,
                'artifacts': artifacts,
            }

        except Exception as e:
            logger.error("Analysis execution failed: %s", e)
            return {
                'status': 'error',
                'stdout': '',
                'stderr': str(e),
                'exit_code': 1,
            }

    # ------------------------------------------------------------------
    # crawler: Python Runner
    # ------------------------------------------------------------------
    def _execute_crawler(self, task) -> dict:
        try:
            module = getattr(task, 'module', 'hot_topics')
            script = getattr(task, 'script', '') or ''

            # 检测 RSS 配置
            if script.strip().startswith('{'):
                try:
                    cfg = json.loads(script)
                    if cfg.get('type') == 'user_rss' and cfg.get('user_source_ids'):
                        return self._execute_user_rss(task, cfg)
                    if cfg.get('type') == 'rss' and cfg.get('source_ids'):
                        return self._execute_rss(task, cfg)
                except json.JSONDecodeError:
                    pass

            runner_map = {
                'hot_topics': ('crawlers.hot_topics.runner', 'HotTopicsRunner'),
                'policy': ('crawlers.policy.runner', 'PolicyRunner'),
                'exchange': ('crawlers.exchange.runner', 'ExchangeRunner'),
                'financial': ('crawlers.financial.runner', 'FinancialRunner'),
            }

            if module not in runner_map:
                return {
                    'status': 'error',
                    'stdout': '',
                    'stderr': f'Unknown crawler module: {module}',
                    'exit_code': 1,
                }

            mod_path, cls_name = runner_map[module]
            mod = importlib.import_module(mod_path)
            runner_cls = getattr(mod, cls_name)
            runner = runner_cls()
            results = runner.run_all()

            success_count = sum(1 for r in results if r.get('status') == 'success')
            stdout_lines = [f'{r.get("platform","?")}: {r.get("status","?")} ({r.get("item_count",0)} items)' for r in results]
            artifacts = self._scan_artifacts(task)

            return {
                'status': 'success' if success_count > 0 else 'failed',
                'stdout': '\n'.join(stdout_lines),
                'stderr': '',
                'exit_code': 0 if success_count > 0 else 1,
                'artifacts': artifacts,
            }
        except Exception as e:
            logger.error("Crawler execution failed: %s", e)
            return {
                'status': 'error',
                'stdout': '',
                'stderr': str(e),
                'exit_code': 1,
            }

    # ------------------------------------------------------------------
    # crawler/rss: RSS 数据源采集
    # ------------------------------------------------------------------
    def _execute_rss(self, task, cfg: dict) -> dict:
        try:
            import feedparser
            from app import db
            from app.models.rss_source import RssSource
        except ImportError as e:
            return {'status': 'error', 'stdout': '', 'stderr': f'Missing dependency: {e}', 'exit_code': 1}

        source_ids = cfg.get('source_ids', [])
        if not source_ids:
            return {'status': 'error', 'stdout': '', 'stderr': 'No source_ids in config', 'exit_code': 1}

        # 查询数据源
        sources = RssSource.query.filter(RssSource.id.in_(source_ids), RssSource.enabled == True).all()
        if not sources:
            return {'status': 'error', 'stdout': '', 'stderr': 'No enabled sources found', 'exit_code': 1}

        module = getattr(task, 'module', 'rss')
        ts_str = bj_now().strftime('%Y-%m-%dT%H-%M-%S')
        base_output = os.path.join(self.base_dir, 'data', 'raw', module)
        os.makedirs(base_output, exist_ok=True)

        all_items = []
        errors = []
        per_source_counts = []
        for src in sources:
            slug = src.slug or str(src.id)
            try:
                feed = feedparser.parse(src.url)
                if feed.bozo and not feed.entries:
                    errors.append(f'{src.name}: parse error')
                    continue
                items = []
                for entry in feed.entries[:30]:
                    pub = entry.get('published_parsed') or entry.get('updated_parsed')
                    ts = datetime.datetime(*pub[:6]).isoformat() if pub else ''
                    items.append({
                        'title': entry.get('title', ''),
                        'url': entry.get('link', ''),
                        'content': entry.get('summary', ''),
                        'timestamp': ts,
                        'platform': 'rss',
                        'source_name': src.name,
                        'source_slug': slug,
                        'source_category': src.category,
                    })
                all_items.extend(items)

                # 按源写入: {slug}-latest.json + {slug}-{timestamp}.json（空结果跳过）
                if items:
                    src_dir = os.path.join(base_output, slug)
                    os.makedirs(src_dir, exist_ok=True)
                    payload = {
                        'generated_at': bj_now().isoformat(),
                        'source': {'name': src.name, 'slug': slug, 'url': src.url, 'category': src.category},
                        'item_count': len(items),
                        'items': items,
                    }
                    latest_path = os.path.join(src_dir, f'{slug}-latest.json')
                    ts_path = os.path.join(src_dir, f'{slug}-{ts_str}.json')
                    for p in (latest_path, ts_path):
                        with open(p, 'w', encoding='utf-8') as f:
                            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

                per_source_counts.append(f'{slug}: {len(items)} items')
            except Exception as e:
                errors.append(f'{src.name}: {e}')

        artifacts = self._scan_artifacts(task)
        stdout_lines = [f'Fetched {len(all_items)} items from {len(sources)} sources']
        stdout_lines.extend(per_source_counts)
        if errors:
            stdout_lines.append(f'Errors: {len(errors)}')
            stdout_lines.extend(errors[:10])

        return {
            'status': 'success' if all_items else 'warning',
            'stdout': '\n'.join(stdout_lines),
            'stderr': '',
            'exit_code': 0 if all_items else 1,
            'artifacts': artifacts,
        }

    def _execute_user_rss(self, task, cfg: dict) -> dict:
        """Execute RSS crawl for user's personal data sources (disabled in open-source)."""
        return {'status': 'error', 'stdout': '', 'stderr': 'User RSS not supported in open-source version', 'exit_code': 1}
        if not sources:
            return {'status': 'error', 'stdout': '', 'stderr': 'No enabled user sources found', 'exit_code': 1}

    # ------------------------------------------------------------------
    # knowledge: 知识库构建
    # ------------------------------------------------------------------
    def _execute_knowledge(self, task) -> dict:
        try:
            from knowledge_base.kb_manager import KnowledgeBaseManager
            kb = KnowledgeBaseManager()
            result = kb.ingest('all')
            artifacts = self._scan_artifacts(task)

            return {
                'status': result.get('status', 'success'),
                'stdout': json.dumps(result, ensure_ascii=False, indent=2)[:5000],
                'stderr': '',
                'exit_code': 0,
                'artifacts': artifacts,
            }
        except ImportError:
            # knowledge_base 模块还未实现，降级为 script
            logger.warning("knowledge_base module not found, falling back to script")
            return self._execute_script(task)
        except Exception as e:
            logger.error("Knowledge build failed: %s", e)
            return {
                'status': 'error',
                'stdout': '',
                'stderr': str(e),
                'exit_code': 1,
            }

    # ------------------------------------------------------------------
    # report: 报告生成
    # ------------------------------------------------------------------
    def _execute_report(self, task) -> dict:
        """
        报告生成任务支持:
          - 模板 ID: script 字段传 "template:{id}"
          - 自定义提示词: script 字段传 JSON {"prompt": "...", "sources": [...]}
          - 趋势参考: 读取历史报告对比
          - 使用 anthropic SDK harness 模式
        """
        try:
            script = getattr(task, 'script', '') or ''
            template_id = None
            prompt_template = None
            data_sources = None
            trend_reference = True
            use_harness = True
            rss_source_ids = None

            # 解析配置
            user_id = getattr(task, 'user_id', None)
            use_preferences = False
            if script.startswith('template:'):
                template_id = script.split(':', 1)[1]
            elif script.strip().startswith('{'):
                try:
                    cfg = json.loads(script)
                    template_id = cfg.get('template_id')
                    prompt_template = cfg.get('prompt')
                    data_sources = cfg.get('sources')
                    trend_reference = cfg.get('trend_reference', True)
                    use_harness = cfg.get('use_harness', True)
                    rss_source_ids = cfg.get('rss_source_ids')
                    use_preferences = cfg.get('use_preferences', False)
                except json.JSONDecodeError:
                    pass

            # 调用 ReportExecutor
            from app.scheduler.report_executor import generate_report
            result = generate_report(
                template_id=template_id,
                prompt_template=prompt_template,
                data_sources=data_sources,
                trend_reference=trend_reference,
                use_harness=use_harness,
                rss_source_ids=rss_source_ids,
                task_id=task.id,
                user_id=user_id,
                use_preferences=use_preferences,
            )

            if result.get('success'):
                artifacts = self._scan_artifacts(task)
                stdout_parts = [
                    f"报告已生成: {result.get('filename', 'unknown')}",
                    f"模式: {result.get('model_used', '?')}",
                ]
                # Include agent execution trace if available
                agent_log = result.get('agent_log', '')
                if agent_log:
                    stdout_parts.append('')
                    stdout_parts.append(agent_log)
                return {
                    'status': 'success',
                    'stdout': '\n'.join(stdout_parts),
                    'stderr': '',
                    'exit_code': 0,
                    'artifacts': artifacts,
                }
            else:
                return {
                    'status': 'error',
                    'stdout': result.get('agent_log', ''),
                    'stderr': result.get('error', 'Unknown error'),
                    'exit_code': 1,
                }
        except Exception as e:
            logger.error("Report generation failed: %s", e)
            return {
                'status': 'error',
                'stdout': '',
                'stderr': str(e),
                'exit_code': 1,
            }

    # ------------------------------------------------------------------
    # 产物扫描
    # ------------------------------------------------------------------
    def _scan_artifacts(self, task) -> list:
        artifacts = []
        module = getattr(task, 'module', '')
        data_dir = os.path.join(self.base_dir, 'data', 'raw', module)

        if os.path.exists(data_dir):
            for root, dirs, files in os.walk(data_dir):
                for f in files:
                    if f.endswith('.json'):
                        fpath = os.path.join(root, f)
                        if os.path.islink(fpath) and not os.path.exists(fpath):
                            continue
                        rel = os.path.relpath(fpath, self.base_dir)
                        size = os.path.getsize(fpath)
                        artifacts.append({'name': f, 'path': rel, 'size': size})

        # 扫描 reports（含子目录）
        rdir = os.path.join(self.base_dir, 'reports')
        if os.path.isdir(rdir):
            for root, dirs, files in os.walk(rdir):
                for f in files:
                    if f.endswith('.md') or f.endswith('.json'):
                        fpath = os.path.join(root, f)
                        if os.path.islink(fpath) and not os.path.exists(fpath):
                            continue
                        rel = os.path.relpath(fpath, self.base_dir)
                        artifacts.append({'name': f, 'path': rel, 'size': os.path.getsize(fpath)})

        return artifacts[-20:]

    def execute_async(self, task, callback=None):
        def run():
            result = self.execute(task)
            if callback:
                callback(result)
        t = threading.Thread(target=run)
        t.start()
        return t
