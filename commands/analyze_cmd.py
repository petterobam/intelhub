"""analyze_cmd.py - 分析任务命令"""
import os
import sys
import importlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def analyze_cmd(args):
    """执行分析任务"""
    analysis_type = args.type or 'all'

    ANALYSIS_MAP = {
        'heartbeat': ('analysis.heartbeat.heartbeat_analyzer', 'generate_heartbeat'),
        'resonance': ('analysis.resonance.resonance_analyzer', 'analyze'),
        'trends': ('analysis.trends.trend_analyzer', 'analyze'),
        'aggregate': ('analysis.aggregate.aggregator', 'aggregate_all'),
    }

    if analysis_type not in ANALYSIS_MAP and analysis_type != 'all':
        print(f"Unknown type: {analysis_type}")
        print(f"Available: {', '.join(ANALYSIS_MAP.keys())}")
        return 1

    types_to_run = ANALYSIS_MAP.keys() if analysis_type == 'all' else [analysis_type]

    for atype in types_to_run:
        mod_path, fn_name = ANALYSIS_MAP[atype]
        print(f"\n>>> Running {atype} analysis...")
        try:
            mod = importlib.import_module(mod_path)
            fn = getattr(mod, fn_name)
            result = fn() if callable(fn) else None
            if result:
                import json
                print(f"  OK - {len(json.dumps(result))} chars output")
                if atype == 'aggregate':
                    print(f"    Total items: {result.get('meta', {}).get('total_items', 0)}")
                    print(f"    Platforms: {result.get('meta', {}).get('platform_count', 0)}")
            else:
                print(f"  OK")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    return 0
