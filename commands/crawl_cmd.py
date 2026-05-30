"""crawl_cmd.py - 爬虫执行命令"""
import os
import sys
import importlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def crawl_cmd(args):
    """执行爬虫任务"""
    module = args.module
    platform = args.platform

    RUNNER_MAP = {
        'hot_topics': ('crawlers.hot_topics.runner', 'HotTopicsRunner'),
        'policy': ('crawlers.policy.runner', 'PolicyRunner'),
        'exchange': ('crawlers.exchange.runner', 'ExchangeRunner'),
        'financial': ('crawlers.financial.runner', 'FinancialRunner'),
    }

    if module and module not in RUNNER_MAP:
        print(f"Unknown module: {module}")
        print(f"Available: {', '.join(RUNNER_MAP.keys())}")
        return 1

    modules_to_run = [module] if module else list(RUNNER_MAP.keys())

    total_success = 0
    total_failed = 0

    for mod in modules_to_run:
        mod_path, cls_name = RUNNER_MAP[mod]
        print(f"\n>>> Running {mod} crawler...")
        try:
            mod_obj = importlib.import_module(mod_path)
            runner_cls = getattr(mod_obj, cls_name)
            runner = runner_cls()

            if platform and hasattr(runner, 'run_single'):
                result = runner.run_single(platform)
                results = [result]
            else:
                results = runner.run_all()

            success = sum(1 for r in results if r.get('status') == 'success')
            failed = len(results) - success
            total_success += success
            total_failed += failed

            print(f"  {success}/{len(results)} succeeded")
            for r in results:
                icon = 'OK' if r.get('status') == 'success' else 'FAIL'
                print(f"    [{icon}] {r.get('platform','?')}: {r.get('status','?')} ({r.get('item_count', 0)} items)")

        except Exception as e:
            print(f"  ERROR: {e}")
            total_failed += 1

    print(f"\n=== Total: {total_success} succeeded, {total_failed} failed ===")
    return 0 if total_failed == 0 else 1
