"""提示词优化 API — AI 辅助用户优化报告提示词"""
from flask import Blueprint, request, g
from app.utils.auth import login_required
from app.utils.helpers import standard_response, error_response
from app.api.settings import _get_llm_env

bp = Blueprint('prompt_optimizer', __name__, url_prefix='/api/v1/prompt')

SYSTEM_PROMPT = """你是一个报告提示词优化专家。用户会给你一段现有的提示词和一个优化指令。

你的任务：
1. 理解用户想要的报告风格和目标
2. 保留提示词中的 {变量} 占位符不动（如 {hot_topics}、{rss_data}、{date} 等）
3. 根据用户的指令优化提示词的措辞、结构、分析角度
4. 只输出优化后的完整提示词，不要解释

可用变量：{date} {health} {hot_topics} {policy_data} {exchange_data} {financial_data} {rss_data} {trends} {resonance} {previous_report}"""


@bp.route('/optimize', methods=['POST'])
@login_required
def optimize_prompt():
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    instruction = (data.get('instruction') or '').strip()

    if not prompt:
        return error_response(400, 'prompt 必填')
    if not instruction:
        return error_response(400, 'instruction 必填')

    env, model, api_key = _get_llm_env()
    if not api_key:
        return error_response(400, '请先配置 LLM API Key')

    try:
        import anthropic
        kwargs = {"api_key": api_key}
        base_url = env.get('ANTHROPIC_BASE_URL', '')
        if base_url:
            kwargs["base_url"] = base_url
        client = anthropic.Anthropic(**kwargs)

        user_msg = f"## 当前提示词\n{prompt}\n\n## 优化要求\n{instruction}\n\n请输出优化后的完整提示词。"

        resp = client.messages.create(
            model=model or 'claude-sonnet-4-20250514',
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        optimized = resp.content[0].text
        return standard_response({'optimized': optimized})

    except Exception as e:
        return error_response(500, f'优化失败: {e}')
