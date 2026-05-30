"""Analysis Agents - 三个分析 Agent 的 Runner

HeartbeatAgent: 投资心跳分析 (每天4次)
InsightAgent: 洞察报告生成 (每天2次)
OptimizationAgent: 自优化分析 (每小时)
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

from analysis.engine import AnalysisEngine, DATA_DIR

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')


def _load_prompt(name: str) -> str:
    """加载提示词模板"""
    path = os.path.join(PROMPTS_DIR, f'{name}.md')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


def _build_context() -> str:
    """构建初始上下文 - 数据概览"""
    lines = [f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]

    for module in ['hot_topics', 'policy', 'exchange', 'financial']:
        base = os.path.join(DATA_DIR, module)
        if not os.path.exists(base):
            lines.append(f"## {module}: 无数据")
            continue

        subdirs = sorted([d for d in os.listdir(base)
                         if os.path.isdir(os.path.join(base, d))])
        lines.append(f"## {module} ({len(subdirs)} 个数据源)")

        for sd in subdirs:
            sd_path = os.path.join(base, sd)
            json_files = [f for f in os.listdir(sd_path) if f.endswith('.json')]
            if json_files:
                latest = sorted(json_files, reverse=True)[0]
                mtime = os.path.getmtime(os.path.join(sd_path, latest))
                age_hours = (datetime.now().timestamp() - mtime) / 3600
                lines.append(f"  - {sd}: {len(json_files)}文件, 最新 {age_hours:.1f}小时前")
            else:
                lines.append(f"  - {sd}: 无JSON文件")
        lines.append("")

    return '\n'.join(lines)


class HeartbeatAgent:
    """投资心跳分析"""

    def run(self) -> Dict[str, Any]:
        logger.info("Running heartbeat analysis...")
        engine = AnalysisEngine()
        prompt = _load_prompt('heartbeat')
        context = _build_context()

        result = engine.analyze(
            task_type='heartbeat',
            system_prompt=prompt,
            initial_context=context,
            max_turns=5,
        )

        logger.info("Heartbeat analysis done: %s (backend=%s)",
                     result.get('status'), result.get('backend', 'none'))
        return result


class InsightAgent:
    """洞察报告生成"""

    def run(self) -> Dict[str, Any]:
        logger.info("Running insight analysis...")
        engine = AnalysisEngine()
        prompt = _load_prompt('insight')
        context = _build_context()

        # 添加历史报告参考
        reports_dir = os.path.join(os.path.dirname(DATA_DIR), 'reports', 'insight')
        if os.path.exists(reports_dir):
            prev_reports = sorted(
                [f for f in os.listdir(reports_dir) if f.startswith('insight-') and f.endswith('.md')],
                reverse=True,
            )[:3]
            if prev_reports:
                context += "\n## 历史洞察报告\n"
                for pr in prev_reports:
                    context += f"- {pr}\n"

        result = engine.analyze(
            task_type='insight',
            system_prompt=prompt,
            initial_context=context,
            max_turns=6,
        )

        logger.info("Insight analysis done: %s", result.get('status'))
        return result


class OptimizationAgent:
    """自优化分析"""

    def run(self) -> Dict[str, Any]:
        logger.info("Running optimization analysis...")
        engine = AnalysisEngine()
        prompt = _load_prompt('optimization')
        context = _build_context()

        # 添加系统运行信息
        context += "\n## 系统运行信息\n"
        context += f"- 数据目录: {DATA_DIR}\n"
        context += f"- 分析时间: {datetime.now().isoformat()}\n"

        result = engine.analyze(
            task_type='optimization',
            system_prompt=prompt,
            initial_context=context,
            max_turns=4,
        )

        logger.info("Optimization analysis done: %s", result.get('status'))
        return result
