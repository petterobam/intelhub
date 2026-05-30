"""report_cmd.py - 报告生成命令"""
import os, sys, json
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def report_cmd(args):
    """生成报告"""
    rtype = args.type or 'insight'
    print(f">>> Generating {rtype} report...")
    try:
        if rtype in ('insight', 'daily'):
            from analysis.reports.insight_generator import generate_insight_report
            result = generate_insight_report()
        elif rtype == 'heartbeat':
            from analysis.heartbeat.heartbeat_analyzer import generate_heartbeat
            result = generate_heartbeat()
        else:
            print(f"Unknown report type: {rtype}")
            return 1
        print(f"  OK - Generated report")
        return 0
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()
        return 1
