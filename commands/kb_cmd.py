"""kb_cmd.py - 知识库管理命令"""
import os, sys, json
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def kb_cmd(args):
    """知识库管理"""
    action = args.action

    try:
        from knowledge_base.kb_manager import KnowledgeBaseManager
        kb = KnowledgeBaseManager()

        if action == 'build':
            module = args.module or 'all'
            result = kb.ingest(module)
            print(f"Status: {result['status']}")
            for k, v in result.get('build_results', {}).items():
                if isinstance(v, dict):
                    print(f"  {k}: {v.get('items', v.get('nodes', v.get('industries', 'ok')))}")

        elif action == 'stats':
            stats = kb.stats()
            for mod, data in stats.get('modules', {}).items():
                if isinstance(data, dict):
                    print(f"  {mod}: {data.get('status', '?')} (age={data.get('age_minutes', '?')}min)")

        elif action == 'search':
            query = args.query
            if not query:
                print("Usage: intelhub kb search <query>")
                return 1
            results = kb.search(query)
            print(f"Found {len(results)} results for '{query}':")
            for r in results[:10]:
                print(f"  - {r.get('title', r.get('name', ''))[:60]}")

        else:
            print(f"Unknown action: {action}")
            print("Available: build, stats, search")
            return 1

        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        return 1
