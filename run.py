#!/usr/bin/env python3
"""IntelHub CLI - 统一命令行入口

用法:
  python3 run.py status                # 查看系统状态
  python3 run.py server [--port 18923] # 启动 Web 服务
  python3 run.py crawl [module]        # 执行爬虫 (hot_topics/policy/exchange/financial)
  python3 run.py analyze [type]        # 执行分析 (heartbeat/resonance/trends/aggregate)
  python3 run.py report [type]         # 生成报告 (insight/heartbeat)
  python3 run.py kb <action>          # 知识库 (build/stats/search)
  python3 run.py task <action>         # 任务管理 (list/run/enable/disable)

示例:
  python3 run.py status
  python3 run.py crawl hot_topics
  python3 run.py crawl               # 执行所有爬虫
  python3 run.py analyze heartbeat
  python3 run.py analyze all
  python3 run.py kb stats
  python3 run.py kb search 华为
  python3 run.py task list
  python3 run.py task run <task_id>
  python3 run.py server --port 18923
"""
import argparse
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def cmd_status(args):
    from commands.status_cmd import status_cmd
    return status_cmd(args)


def cmd_server(args):
    from app import create_app
    print(f"Starting IntelHub API server on http://{args.host}:{args.port}")
    print(f"API docs: http://localhost:{args.port}/api/v1/")
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


def cmd_crawl(args):
    from commands.crawl_cmd import crawl_cmd
    return crawl_cmd(args)


def cmd_analyze(args):
    from commands.analyze_cmd import analyze_cmd
    return analyze_cmd(args)


def cmd_report(args):
    from commands.report_cmd import report_cmd
    return report_cmd(args)


def cmd_kb(args):
    from commands.kb_cmd import kb_cmd
    return kb_cmd(args)


def cmd_task(args):
    from commands.task_cmd import task_cmd
    return task_cmd(args)


def main():
    parser = argparse.ArgumentParser(
        description="IntelHub CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    sub = parser.add_subparsers(dest='command', help='Available commands')

    # status
    p_status = sub.add_parser('status', help='View system status')
    p_status.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    p_status.set_defaults(func=cmd_status)

    # server
    p_server = sub.add_parser('server', help='Start web server')
    p_server.add_argument('--port', type=int, default=18923, help='Port (default: 18923)')
    p_server.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    p_server.add_argument('--debug', action='store_true', default=True, help='Debug mode')
    p_server.add_argument('--no-debug', dest='debug', action='store_false', help='Disable debug')
    p_server.set_defaults(func=cmd_server)

    # crawl
    p_crawl = sub.add_parser('crawl', help='Run crawler tasks')
    p_crawl.add_argument('module', nargs='?', choices=['hot_topics', 'policy', 'exchange', 'financial'], help='Crawler module')
    p_crawl.add_argument('--platform', help='Specific platform (if supported)')
    p_crawl.set_defaults(func=cmd_crawl)

    # analyze
    p_analyze = sub.add_parser('analyze', help='Run analysis tasks')
    p_analyze.add_argument('type', nargs='?', help='Analysis type (heartbeat/resonance/trends/aggregate/all)')
    p_analyze.set_defaults(func=cmd_analyze)

    # report
    p_report = sub.add_parser('report', help='Generate reports')
    p_report.add_argument('type', nargs='?', help='Report type (insight/heartbeat)')
    p_report.set_defaults(func=cmd_report)

    # kb
    p_kb = sub.add_parser('kb', help='Knowledge base management')
    p_kb.add_argument('action', choices=['build', 'stats', 'search', 'rebuild'], help='Action')
    p_kb.add_argument('--module', help='Specific module (topics/industry/graph/all)')
    p_kb.add_argument('--query', help='Search query (for search action)')
    p_kb.set_defaults(func=cmd_kb)

    # task
    p_task = sub.add_parser('task', help='Task management')
    p_task.add_argument('action', choices=['list', 'run', 'enable', 'disable'], help='Action')
    p_task.add_argument('task_id', nargs='?', help='Task ID (for run/enable/disable)')
    p_task.set_defaults(func=cmd_task)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
