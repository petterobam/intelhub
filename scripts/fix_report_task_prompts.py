"""修复所有报告任务的 script JSON，确保 prompt 字段合法可解析。

问题：SQL INSERT 中的 prompt 文本包含中文引号和换行符，
     导致 JSON 解析失败，前端 custom_prompt 读不到提示词。
方案：用 Python 重新构建合法 JSON，写入 DB。
"""
import json
import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'intel_hub.db')

# ── 各任务的完整配置 ──────────────────────────────────────────
# 每个 key 是 task id，value 是 script JSON 里的完整 prompt

TASK_PROMPTS = {
    'film_daily': {
        'template_id': 'template:daily',
        'prompt': (
            '你是一位资深的影视行业数据洞察分析师，专注于影视娱乐、AIGC与内容产业的深度观察与趋势研判。\n\n'
            '## 当前时间\n{date}\n\n'
            '## 系统健康状态\n{health}\n\n'
            '## 历史趋势对比（与上次报告对比）\n{previous_report}\n\n'
            '## 跨平台热点（共振分析）\n{resonance}\n\n'
            '## 话题趋势\n{trends}\n\n'
            '## 各平台数据详情\n### 热点话题\n{hot_topics}\n\n'
            '### 影视/演出/游戏数据\n{exchange_data}\n\n'
            '### 泛娱乐与流行文化资讯\n{rss_data}\n\n'
            '---\n\n'
            '请先判断今天是周几。根据星期执行不同任务：\n\n'
            '### 如果今天是周一 → 生成周报\n\n'
            '汇总过去7天的报告数据（{previous_report}），生成影视行业周报：\n\n'
            '**🎬 影视行业周报 | {date}**\n\n'
            '1. **本周核心热点 TOP 3** — 按影响力排序，每个热点说明：是什么 → 为什么火 → 后续走向\n'
            '2. **关键转折信号** — 本周出现的行业拐点、意外事件或认知反转\n'
            '3. **持续性趋势** — 连续多天升温的方向及深层逻辑\n'
            '4. **AIGC × 影视本周回顾** — AI 技术在影视领域的进展、值得关注的项目\n'
            '5. **下周展望** — 即将上映的重点影片、预计会发酵的事件、重点关注方向\n\n'
            '### 如果今天是周二至周日 → 生成日报\n\n'
            '1. **综合扫描**：消化上述所有数据，聚焦影视行业和 AIGC\n'
            '2. **新旧对比**：对比 {previous_report}，找出新发现和变化\n'
            '3. **洞察生成**：按以下结构输出\n\n'
            '**🎬 影视行业洞察 | {date}**\n\n'
            '1. **今日核心发现** — 一句话概括 + 3 条关键行业信号（有数据/事件支撑）\n'
            '2. **影视产业动态** — 院线票房、流媒体平台、内容制作、行业政策\n'
            '3. **AIGC × 影视** — AI 制作应用进展、开源项目/工具更新、商业化进展\n'
            '4. **市场与资本** — 影视公司股价、投融资并购、行业景气度\n'
            '5. **短期趋势研判** — 持续关注方向、转折信号、下周前瞻\n\n'
            '## 约束\n'
            '- 如果没有差异化洞察，输出：无新洞察，静默结束\n'
            '- 专业但不枯燥，有观点有判断\n'
            '- Markdown 格式，善用加粗和列表\n'
            '- 不要在末尾添加查看完整报告等链接文字'
        ),
        'sources': ['rss'],
        'trend_reference': True,
        'use_harness': True,
        'rss_source_ids': [66, 67, 80, 81, 425, 426, 427, 432, 433],
        'model': 'glm-5.1',
    },

    'tech_daily': {
        'template_id': 'template:daily',
        'prompt': (
            '你是一位专注于影视技术创新的趋势洞察分析师，深度跟踪 AI 与开源技术驱动的内容生产变革。\n\n'
            '## 当前时间\n{date}\n\n'
            '## 系统健康状态\n{health}\n\n'
            '## 历史趋势对比（与上次报告对比）\n{previous_report}\n\n'
            '## 跨平台热点（共振分析）\n{resonance}\n\n'
            '## 话题趋势\n{trends}\n\n'
            '## 各平台数据详情\n### 热点话题\n{hot_topics}\n\n'
            '### 政策与科技动态\n{policy_data}\n\n'
            '### 技术与开源资讯\n{rss_data}\n\n'
            '---\n\n'
            '请先判断今天是周几。根据星期执行不同任务：\n\n'
            '### 如果今天是周一 → 生成周报\n\n'
            '汇总过去7天的报告数据（{previous_report}），生成影视技术周报：\n\n'
            '**🤖 影视技术周报 | {date}**\n\n'
            '1. **本周核心技术动向 TOP 3** — 按重要性排序，每项说明：技术突破 → 影响范围 → 应用前景\n'
            '2. **关键转折信号** — 技术路线的范式转移、重大版本发布\n'
            '3. **开源项目热词** — Star 增长最快的影视/AIGC 项目、新冒出值得关注的项目、技术栈趋势\n'
            '4. **AI 生成技术本周回顾** — 视频生成/图像生成/3D生成/音频生成各赛道进展\n'
            '5. **下周技术展望** — 预计发布的重要更新、值得关注的方向、开发者实践建议\n\n'
            '### 如果今天是周二至周日 → 生成日报\n\n'
            '重点跟踪：GitHub Trending 影视/AIGC 热门仓库、Hugging Face 模型更新、影视技术进展\n\n'
            '**🤖 影视技术趋势洞察 | {date}**\n\n'
            '1. **概览** — 今日技术圈最重要的 1-2 个突破\n'
            '2. **AI 生成技术** — 视频生成模型进展、图像/3D/音频生成更新、模型能力对比\n'
            '3. **剪辑与后期** — AI 辅助剪辑工具、特效/渲染技术、开源后期工具\n'
            '4. **配音与音频** — AI 配音/语音克隆、音乐生成 AI\n'
            '5. **剧本与创作** — AI 剧本辅助工具、内容创作自动化\n'
            '6. **开源代码库亮点** — 新增/热门项目（附 GitHub 链接、Star 趋势）\n'
            '7. **短期趋势展望** — 1-2 周技术演进预判\n\n'
            '## 约束\n'
            '- 如果没有差异化洞察，输出：无新洞察，静默结束\n'
            '- 技术内容要有深度，开源项目给出具体技术细节和 Star/Fork 数据\n'
            '- 使用 Markdown 格式\n'
            '- 不要在末尾添加查看完整报告等链接文字'
        ),
        'sources': ['rss'],
        'trend_reference': True,
        'use_harness': True,
        'rss_source_ids': [275, 276, 277, 280, 281, 283, 284, 286, 289, 293, 294, 295, 297, 298, 299, 300, 301, 302, 304, 306, 309, 311, 314, 315, 329, 335, 349, 357, 360, 365, 367, 371, 373, 374, 377, 378, 385],
        'model': 'glm-5.1',
    },

    'finance_daily': {
        'template_id': 'template:daily',
        'prompt': (
            '你是一位资深的金融市场数据洞察分析师，擅长从海量碎片化数据中抽丝剥茧，挖掘市场暗线与跨资产联动规律。\n\n'
            '## 当前时间\n{date}\n\n'
            '## 系统健康状态\n{health}\n\n'
            '## 历史趋势对比（与上次报告对比）\n{previous_report}\n\n'
            '## 跨平台热点（共振分析）\n{resonance}\n\n'
            '## 话题趋势\n{trends}\n\n'
            '## 各平台数据详情\n### 热点话题\n{hot_topics}\n\n'
            '### 政策动态\n{policy_data}\n\n'
            '### 交易所公告\n{exchange_data}\n\n'
            '### 财经资讯\n{financial_data}\n\n'
            '### 全球资讯与舆情\n{rss_data}\n\n'
            '---\n\n'
            '请先判断今天是周几。根据星期执行不同任务：\n\n'
            '### 如果今天是周一 → 生成周报\n\n'
            '汇总过去7天的报告数据（{previous_report}），生成市场金融周报：\n\n'
            '**📊 市场金融周报 | {date}**\n\n'
            '1. **本周核心热点 TOP 3** — 按市场影响力排序：驱动逻辑 → 资金反应 → 后续推演\n'
            '2. **关键转折信号** — 市场风格切换、政策拐点、与上周预判的偏差\n'
            '3. **持续性趋势** — 连续多周演绎的主线、板块轮动路径、资金偏好变化\n'
            '4. **本周策略复盘** — 上周建议的执行效果、验证/证伪判断\n'
            '5. **下周展望** — 重要事件日历、看多/看空方向、风险点、战术与战略建议\n\n'
            '### 如果今天是周二至周日 → 生成日报\n\n'
            '综合分析所有数据，聚焦金融市场与宏观经济：\n\n'
            '**📊 市场金融洞察 | {date}**\n\n'
            '1. **核心定调** — 一句话概括当日交易逻辑 + 3 条预期差/异动信号（附数据）\n'
            '2. **宏观与政策** — 政策发布及意图、宏观数据解读、全球环境变化\n'
            '3. **资金与流动性** — 主力资金流向、板块轮动、北向/外资动向、流动性水温\n'
            '4. **市场热点深度推演**（2-3个主题）— 驱动逻辑、映射板块与标的、乐观/中性/悲观情景\n'
            '5. **风险预警** — 高危（红牌）、灰犀牛（黄牌）、关键指标监控\n'
            '6. **短期趋势研判** — 1-2 周方向预判、策略建议\n\n'
            '## 约束\n'
            '- 如果没有差异化洞察，输出：无新洞察，静默结束\n'
            '- 机构投研风格，多用金融术语\n'
            '- Markdown 格式，核心数据加粗\n'
            '- 不要在末尾添加查看完整报告等链接文字'
        ),
        'sources': ['hot_topics', 'policy', 'exchange', 'financial', 'rss'],
        'trend_reference': True,
        'use_harness': True,
        'rss_source_ids': [68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 305],
        'model': 'glm-5.1',
    },
}


def _inject_weekly_hint(original_prompt: str, search_text: str, weekly_block: str, daily_prefix: str) -> str:
    """在原始 prompt 中注入周报判断逻辑"""
    if '请先判断今天是周几' in original_prompt:
        return original_prompt  # 已有周报逻辑
    if search_text not in original_prompt:
        return original_prompt  # 找不到插入点，不改
    replacement = weekly_block + '\n\n' + daily_prefix + search_text
    return original_prompt.replace(search_text, replacement, 1)


# 旧任务的周报注入配置
WEEKLY_INJECTIONS = {
    '72966fe8': {
        'search': '请深度消化上述所有数据，剔除市场噪音，寻找预期差与核心主线。请严格按照以下 Markdown 结构输出一份极具专业深度、逻辑严密、结论干脆的市场洞察报告。',
        'weekly': (
            '请先判断今天是周几，根据星期执行不同任务：\n\n'
            '**如果今天是周一 → 生成周报**\n'
            '汇总过去7天的报告数据（{previous_report}），按以下结构输出：\n'
            '1. **本周核心热点 TOP 3** — 按市场影响力排序，每个热点：驱动逻辑 → 资金反应 → 后续推演\n'
            '2. **关键转折信号** — 市场风格切换、政策拐点、与上周预判的偏差\n'
            '3. **持续性趋势** — 连续多周演绎的主线、板块轮动路径、资金偏好变化\n'
            '4. **本周策略复盘** — 上周建议的执行效果、验证/证伪判断\n'
            '5. **下周展望** — 重要事件日历（经济数据、政策会议）、看多/看空方向、风险点、战术与战略建议\n'
            '标题格式：《市场洞察周报_{date}》\n\n'
            '**如果是周二至周日 → 生成日报**'
        ),
        'daily_prefix': '',
    },
    '45bef843': {
        'search': '请生成一份结构清晰、覆盖面广的每日综合洞察报告。不仅要关注投资与金融市场，还要全面拆解宏观经济、政策走向、科技前沿及社会生活等领域的核心动态。报告要求如下：',
        'weekly': (
            '请先判断今天是周几，根据星期执行不同任务：\n\n'
            '**如果今天是周一 → 生成周报**\n'
            '汇总过去7天的报告数据（{previous_report}），按以下结构输出：\n'
            '1. **本周核心事件 TOP 5** — 按影响力排序，涵盖政经、科技、社会、金融全领域\n'
            '2. **关键转折与意外** — 本周出现的重大拐点或超预期事件\n'
            '3. **持续性主题追踪** — 连续多天持续升温的方向及深层逻辑\n'
            '4. **跨领域联动分析** — 政策×科技×市场×社会生活的交叉影响\n'
            '5. **下周前瞻** — 重要事件预告、可能发酵的热点、风险预警\n'
            '标题格式：《综合洞察周报_{date}》\n\n'
            '**如果是周二至周日 → 生成日报**\n'
            '不仅要关注投资与金融市场，还要全面拆解宏观经济、政策走向、科技前沿及社会生活等领域的核心动态。报告要求如下：'
        ),
        'daily_prefix': '',
    },
    '4ae82d23': {
        'search': '请生成一份结构清晰、轻松易读的每日生活娱乐风向报告，要求：',
        'weekly': (
            '请先判断今天是周几，根据星期执行不同任务：\n\n'
            '**如果今天是周一 → 生成周报**\n'
            '汇总过去7天的报告数据（{previous_report}），按以下结构输出：\n'
            '1. **本周吃瓜大事件 TOP 5** — 按热度排序，每个事件：起因 → 发酵 → 现状 → 后续\n'
            '2. **本周破圈话题** — 跨平台共振最强烈的 2-3 个话题\n'
            '3. **流行趋势变迁** — 本周新冒出的梗/穿搭/生活方式，以及消退的热点\n'
            '4. **塌房/争议复盘** — 本周公关危机、饭圈冲突、监管动作汇总\n'
            '5. **下周文娱消费预告** — 值得期待的电影/游戏/演出/活动\n'
            '标题格式：《生活娱乐风向周报_{date}》\n\n'
            '**如果是周二至周日 → 生成日报**'
        ),
        'daily_prefix': '',
    },
}


def _extract_broken_json(raw: str) -> dict:
    """从损坏的 JSON 中提取配置字段"""
    import re
    m = re.search(r'"prompt":"(.*?)","sources"', raw, re.DOTALL)
    prompt = m.group(1).replace('\\n', '\n').replace('\\"', '"') if m else ''
    m2 = re.search(r'"sources":(\[.*?\])', raw)
    sources = json.loads(m2.group(1)) if m2 else []
    m3 = re.search(r'"template_id":"(.*?)"', raw)
    template_id = m3.group(1) if m3 else ''
    trend = '"trend_reference":true' in raw
    harness = '"use_harness":true' in raw
    m4 = re.search(r'"model":"(.*?)"', raw)
    model = m4.group(1) if m4 else ''
    m5 = re.search(r'"rss_source_ids":(\[.*?\])', raw)
    rss_ids = json.loads(m5.group(1)) if m5 else []
    return {
        'template_id': template_id,
        'prompt': prompt,
        'sources': sources,
        'trend_reference': trend,
        'use_harness': harness,
        'model': model,
        'rss_source_ids': rss_ids,
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    updated = 0

    # 1. 修复新任务（完整重写 script JSON）
    for task_id, cfg in TASK_PROMPTS.items():
        script_json = json.dumps(cfg, ensure_ascii=False)
        conn.execute('UPDATE scheduled_tasks SET script = ? WHERE id = ?', (script_json, task_id))
        updated += 1
        print(f'  [{task_id}] Fixed (rewrite)')

    # 2. 修复旧任务（提取损坏 JSON 的 prompt，注入周报，重建合法 JSON）
    for task_id, inj in WEEKLY_INJECTIONS.items():
        row = conn.execute('SELECT script FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            print(f'  [{task_id}] NOT FOUND, skip')
            continue

        raw = row[0]
        # 尝试直接解析
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError:
            # JSON 坏了，用正则提取
            cfg = _extract_broken_json(raw)
            print(f'  [{task_id}] Extracted from broken JSON')

        # 注入周报逻辑
        prompt = cfg.get('prompt', '')
        prompt = _inject_weekly_hint(
            prompt,
            inj['search'],
            inj['weekly'],
            inj.get('daily_prefix', ''),
        )
        cfg['prompt'] = prompt

        script_json = json.dumps(cfg, ensure_ascii=False)
        conn.execute('UPDATE scheduled_tasks SET script = ? WHERE id = ?', (script_json, task_id))
        updated += 1
        print(f'  [{task_id}] Fixed (weekly injected)')

    conn.commit()
    conn.close()

    # 验证
    print(f'\nUpdated {updated} tasks. Verifying...')
    conn = sqlite3.connect(DB_PATH)
    all_ok = True
    for row in conn.execute("SELECT id, name, script FROM scheduled_tasks WHERE task_type='report'"):
        try:
            cfg = json.loads(row[2])
            prompt = cfg.get('prompt', '')
            has_weekly = '请先判断今天是周几' in prompt
            print(f'  {row[0]} | {row[1]} | prompt={len(prompt)}chars | weekly={"YES" if has_weekly else "NO"}')
        except Exception as e:
            print(f'  {row[0]} | {row[1]} | STILL BROKEN: {e}')
            all_ok = False
    conn.close()

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
