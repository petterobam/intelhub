-- 新增 3 个基础报告任务（日报 + 周报合一，每周一自动生成周报格式）

-- 1. 影视行业洞察报告（每天 08:00，周一生成周报）
INSERT OR IGNORE INTO scheduled_tasks (id, name, task_type, module, script, description, tags, schedule_type, schedule_config, enabled, status, deliver_to, created_at, updated_at)
VALUES (
  'film_daily',
  '影视行业洞察报告',
  'report',
  'analysis',
  '{"template_id":"template:daily","prompt":"你是一位资深的影视行业数据洞察分析师，专注于影视娱乐、AIGC与内容产业的深度观察与趋势研判。\n\n## 当前时间\n{date}\n\n## 系统健康状态\n{health}\n\n## 历史趋势对比（与上次报告对比）\n{previous_report}\n\n## 跨平台热点（共振分析）\n{resonance}\n\n## 话题趋势\n{trends}\n\n## 各平台数据详情\n### 热点话题\n{hot_topics}\n\n### 影视/演出/游戏数据\n{exchange_data}\n\n### 泛娱乐与流行文化资讯\n{rss_data}\n\n---\n\n请先判断今天是周几。根据星期执行不同任务：\n\n### 如果今天是周一 → 生成周报\n\n汇总过去7天的报告数据（{previous_report}），生成影视行业周报：\n\n**🎬 影视行业周报 | {date}**\n\n1. **本周核心热点 TOP 3** — 按影响力排序，每个热点说明：是什么 → 为什么火 → 后续走向\n2. **关键转折信号** — 本周出现的行业拐点、意外事件或认知反转\n3. **持续性趋势** — 连续多天升温的方向及深层逻辑\n4. **AIGC × 影视本周回顾** — AI 技术在影视领域的进展、值得关注的项目\n5. **下周展望** — 即将上映的重点影片、预计会发酵的事件、重点关注方向\n\n### 如果今天是周二至周日 → 生成日报\n\n1. **综合扫描**：消化上述所有数据，聚焦影视行业和 AIGC\n2. **新旧对比**：对比 {previous_report}，找出新发现和变化\n3. **洞察生成**：按以下结构输出\n\n**🎬 影视行业洞察 | {date}**\n\n1. **今日核心发现** — 一句话概括 + 3 条关键行业信号（有数据/事件支撑）\n2. **影视产业动态** — 院线票房、流媒体平台、内容制作、行业政策\n3. **AIGC × 影视** — AI 制作应用进展、开源项目/工具更新、商业化进展\n4. **市场与资本** — 影视公司股价、投融资并购、行业景气度\n5. **短期趋势研判** — 持续关注方向、转折信号、下周前瞻\n\n## 约束\n- 如果没有差异化洞察，输出：无新洞察，静默结束\n- 专业但不枯燥，有观点有判断\n- Markdown 格式，善用加粗和列表\n- 不要在末尾添加"查看完整报告"等链接文字","sources":["rss"],"trend_reference":true,"use_harness":true,"rss_source_ids":[66,67,80,81,425,426,427,432,433],"model":"glm-5.1"}',
  '影视行业与AIGC趋势洞察，每天08:00生成，周一自动切周报格式',
  '影视,AIGC,日报',
  'cron',
  '{"type": "cron", "cron": "0 8 * * *"}',
  1,
  'idle',
  'local',
  datetime('now'),
  datetime('now')
);

-- 2. 影视技术趋势洞察报告（每天 09:00，周一生成周报）
INSERT OR IGNORE INTO scheduled_tasks (id, name, task_type, module, script, description, tags, schedule_type, schedule_config, enabled, status, deliver_to, created_at, updated_at)
VALUES (
  'tech_daily',
  '影视技术趋势洞察报告',
  'report',
  'analysis',
  '{"template_id":"template:daily","prompt":"你是一位专注于影视技术创新的趋势洞察分析师，深度跟踪 AI 与开源技术驱动的内容生产变革。\n\n## 当前时间\n{date}\n\n## 系统健康状态\n{health}\n\n## 历史趋势对比（与上次报告对比）\n{previous_report}\n\n## 跨平台热点（共振分析）\n{resonance}\n\n## 话题趋势\n{trends}\n\n## 各平台数据详情\n### 热点话题\n{hot_topics}\n\n### 政策与科技动态\n{policy_data}\n\n### 技术与开源资讯\n{rss_data}\n\n---\n\n请先判断今天是周几。根据星期执行不同任务：\n\n### 如果今天是周一 → 生成周报\n\n汇总过去7天的报告数据（{previous_report}），生成影视技术周报：\n\n**🤖 影视技术周报 | {date}**\n\n1. **本周核心技术动向 TOP 3** — 按重要性排序，每项说明：技术突破 → 影响范围 → 应用前景\n2. **关键转折信号** — 技术路线的范式转移、重大版本发布\n3. **开源项目热词** — Star 增长最快的影视/AIGC 项目、新冒出值得关注的项目、技术栈趋势\n4. **AI 生成技术本周回顾** — 视频生成/图像生成/3D生成/音频生成各赛道进展\n5. **下周技术展望** — 预计发布的重要更新、值得关注的方向、开发者实践建议\n\n### 如果今天是周二至周日 → 生成日报\n\n重点跟踪：GitHub Trending 影视/AIGC 热门仓库、Hugging Face 模型更新、影视技术进展（剧本AI、AI剪辑、配音克隆、开源视频生成、3D生成）\n\n**🤖 影视技术趋势洞察 | {date}**\n\n1. **概览** — 今日技术圈最重要的 1-2 个突破\n2. **AI 生成技术** — 视频生成模型进展、图像/3D/音频生成更新、模型能力对比\n3. **剪辑与后期** — AI 辅助剪辑工具、特效/渲染技术、开源后期工具\n4. **配音与音频** — AI 配音/语音克隆、音乐生成 AI\n5. **剧本与创作** — AI 剧本辅助工具、内容创作自动化\n6. **开源代码库亮点** — 新增/热门项目（附 GitHub 链接、Star 趋势）\n7. **短期趋势展望** — 1-2 周技术演进预判\n\n## 约束\n- 如果没有差异化洞察，输出：无新洞察，静默结束\n- 技术内容要有深度，开源项目给出具体技术细节和 Star/Fork 数据\n- 使用 Markdown 格式\n- 不要在末尾添加"查看完整报告"等链接文字","sources":["rss"],"trend_reference":true,"use_harness":true,"rss_source_ids":[275,276,277,280,281,283,284,286,289,293,294,295,297,298,299,300,301,302,304,306,309,311,314,315,329,335,349,357,360,365,367,371,373,374,377,378,385],"model":"glm-5.1"}',
  '影视技术创新趋势洞察，聚焦AI与开源，每天09:00生成，周一自动切周报格式',
  '影视技术,AI,开源,日报',
  'cron',
  '{"type": "cron", "cron": "0 9 * * *"}',
  1,
  'idle',
  'local',
  datetime('now'),
  datetime('now')
);

-- 3. 通用金融洞察报告（每天 09:30，周一生成周报）
INSERT OR IGNORE INTO scheduled_tasks (id, name, task_type, module, script, description, tags, schedule_type, schedule_config, enabled, status, deliver_to, created_at, updated_at)
VALUES (
  'finance_daily',
  '通用金融洞察报告',
  'report',
  'analysis',
  '{"template_id":"template:daily","prompt":"你是一位资深的金融市场数据洞察分析师，擅长从海量碎片化数据中抽丝剥茧，挖掘市场暗线与跨资产联动规律。\n\n## 当前时间\n{date}\n\n## 系统健康状态\n{health}\n\n## 历史趋势对比（与上次报告对比）\n{previous_report}\n\n## 跨平台热点（共振分析）\n{resonance}\n\n## 话题趋势\n{trends}\n\n## 各平台数据详情\n### 热点话题\n{hot_topics}\n\n### 政策动态\n{policy_data}\n\n### 交易所公告\n{exchange_data}\n\n### 财经资讯\n{financial_data}\n\n### 全球资讯与舆情\n{rss_data}\n\n---\n\n请先判断今天是周几。根据星期执行不同任务：\n\n### 如果今天是周一 → 生成周报\n\n汇总过去7天的报告数据（{previous_report}），生成市场金融周报：\n\n**📊 市场金融周报 | {date}**\n\n1. **本周核心热点 TOP 3** — 按市场影响力排序：驱动逻辑 → 资金反应 → 后续推演\n2. **关键转折信号** — 市场风格切换、政策拐点、与上周预判的偏差\n3. **持续性趋势** — 连续多周演绎的主线、板块轮动路径、资金偏好变化\n4. **本周策略复盘** — 上周建议的执行效果、哪些判断被验证/证伪\n5. **下周展望** — 重要事件日历、看多/看空方向、风险点、战术与战略建议\n\n### 如果今天是周二至周日 → 生成日报\n\n综合分析所有数据，聚焦金融市场与宏观经济：\n\n**📊 市场金融洞察 | {date}**\n\n1. **核心定调** — 一句话概括当日交易逻辑 + 3 条预期差/异动信号（附数据）\n2. **宏观与政策** — 政策发布及意图、宏观数据解读、全球环境变化\n3. **资金与流动性** — 主力资金流向、板块轮动、北向/外资动向、流动性水温\n4. **市场热点深度推演**（2-3个主题）— 驱动逻辑、映射板块与标的、乐观/中性/悲观情景\n5. **风险预警** — 高危（红牌）、灰犀牛（黄牌）、关键指标监控\n6. **短期趋势研判** — 1-2 周方向预判、策略建议\n\n## 约束\n- 如果没有差异化洞察，输出：无新洞察，静默结束\n- 机构投研风格，多用金融术语\n- Markdown 格式，核心数据加粗\n- 不要在末尾添加"查看完整报告"等链接文字","sources":["hot_topics","policy","exchange","financial","rss"],"trend_reference":true,"use_harness":true,"rss_source_ids":[68,69,70,71,72,73,74,75,76,77,78,79,305],"model":"glm-5.1"}',
  '通用金融市场洞察，每天09:30生成，周一自动切周报格式',
  '金融,市场,财经,日报',
  'cron',
  '{"type": "cron", "cron": "30 9 * * *"}',
  1,
  'idle',
  'local',
  datetime('now'),
  datetime('now')
);
