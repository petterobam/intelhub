"""ReportTemplate model - 报告模板管理（支持自定义提示词+数据筛选+趋势参考）"""
import uuid, json
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, JSON

from app import db
from app.utils.helpers import bj_now


class ReportTemplate(db.Model):
    """报告模板

    提示词支持变量替换:
      {hot_topics}  - 热点数据摘要
      {policy_data} - 政策数据摘要
      {exchange_data} - 交易所公告摘要
      {financial_data} - 财经数据摘要
      {rss_data}   - RSS 数据源摘要
      {trends}     - 趋势分析结果
      {resonance}  - 共振分析结果
      {health}     - 系统健康状态
      {previous_report} - 历史报告摘要（趋势参考）
      {date}       - 当前日期
    """
    __tablename__ = 'report_templates'

    id            = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    name          = Column(String(128), nullable=False, index=True)
    description   = Column(Text, default='')
    # 提示词模板（包含 {变量} 占位符）
    prompt_template = Column(Text, nullable=False)
    # 数据源筛选（哪些平台的数据要纳入报告）
    data_sources  = Column(JSON, default=list)  # ['hot_topics','policy','exchange','financial']
    # 是否启用趋势参考（对比历史报告）
    trend_reference = Column(Boolean, default=True)
    # 执行参数
    max_items_per_source = Column(Integer, default=50)  # 每个数据源最多取多少条
    # 关联的定时任务ID
    task_id       = Column(String(16), nullable=True)
    created_at    = Column(DateTime, default=bj_now)
    updated_at    = Column(DateTime, default=bj_now, onupdate=bj_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'prompt_template': self.prompt_template,
            'data_sources': self.data_sources or [],
            'trend_reference': self.trend_reference,
            'max_items_per_source': self.max_items_per_source,
            'task_id': self.task_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def render_prompt(self, context: dict) -> str:
        """将 prompt_template 中的 {变量} 替换为 context 中的值"""
        tmpl = self.prompt_template
        for key, value in context.items():
            placeholder = '{' + key + '}'
            if placeholder in tmpl:
                tmpl = tmpl.replace(placeholder, str(value) if value is not None else '')
        return tmpl

    # ── 默认模板 ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_default_template():
        return ReportTemplate(
            id='default',
            name='默认洞察报告',
            description='系统默认的跨平台热点洞察报告模板',
            prompt_template=REPORT_TEMPLATE_DEFAULT,
            data_sources=['hot_topics', 'policy', 'exchange', 'financial'],
            trend_reference=True,
            max_items_per_source=50,
        )


REPORT_TEMPLATE_DEFAULT = """你是一个专业的投资分析助手。请根据以下数据生成一份投资洞察报告。
{user_preferences}
## 当前时间
{date}

## 系统状态
{health}

## 历史趋势对比
{previous_report}

## 跨平台热点（共振分析）
{resonance}

## 话题趋势
{trends}

## 数据详情
{hot_topics}

{policy_data}
{exchange_data}
{financial_data}

{rss_data}

请生成一份结构清晰的投资洞察报告，包括：
1. 市场情绪总结
2. 关键主题及演变趋势
3. 跨平台共振点（多个平台同时关注的热点）
4. 风险预警（如有）
5. 投资机会线索

报告语言：中文
格式：Markdown
"""
