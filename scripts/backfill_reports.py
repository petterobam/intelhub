"""Backfill Report records from existing report files.

Usage:
    python scripts/backfill_reports.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime


def extract_title(content: str, fallback: str = "") -> str:
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('#'):
            title = line.lstrip('#').strip()
            title = re.sub(r'^[\U0001F300-\U0001F9FF]\s*', '', title)
            if len(title) > 4:
                return title[:120]
    return fallback


def main():
    from app import create_app, db
    from app.models.report import Report
    from app.models.task import ScheduledTask

    app = create_app()
    with app.app_context():
        # Ensure task_id column exists
        try:
            result = db.session.execute(db.text("PRAGMA table_info(reports)"))
            columns = [row[1] for row in result]
            if 'task_id' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE reports ADD COLUMN task_id VARCHAR(36)"
                ))
                db.session.commit()
                print("Added task_id column to reports")
        except Exception as e:
            print(f"Migration check: {e}")

        # Load report tasks
        report_tasks = ScheduledTask.query.filter_by(task_type='report', enabled=True).all()
        print(f"Found {len(report_tasks)} report tasks:")
        for t in report_tasks:
            print(f"  - {t.id}: {t.name}")

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reports_dir = os.path.join(base_dir, 'reports')

        # Scan all .md files
        md_files = []
        for root, dirs, files in os.walk(reports_dir):
            # Skip html directory
            if 'html' in root.split(os.sep):
                continue
            for f in files:
                if f.endswith('.md'):
                    md_files.append(os.path.join(root, f))

        print(f"\nFound {len(md_files)} report .md files")

        # Check existing records
        existing_paths = set()
        for r in Report.query.all():
            if r.file_path:
                existing_paths.add(r.file_path)

        created = 0
        for fpath in sorted(md_files):
            if fpath in existing_paths:
                continue

            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue

            base_name = os.path.splitext(os.path.basename(fpath))[0]
            subdir = os.path.basename(os.path.dirname(fpath))
            title = extract_title(content, fallback=base_name)

            # Try to match task by filename pattern
            task_id = None
            for task in report_tasks:
                # Match by task name keywords in filename
                task_keywords = task.name.replace('报告', '').replace('日报', '').replace('简报', '').strip()
                if task_keywords and task_keywords in base_name:
                    task_id = task.id
                    break

            # Also try to extract date for generated_at
            generated_at = datetime.now()
            date_match = re.search(r'(\d{4})[.-](\d{2})[.-](\d{2})', base_name)
            if date_match:
                try:
                    generated_at = datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
                except ValueError:
                    pass

            report = Report(
                title=title,
                report_type=subdir if subdir in ('agent', 'insight', 'heartbeat') else 'agent',
                file_path=fpath,
                generated_at=generated_at,
                task_id=task_id,
                scope='platform',
            )
            db.session.add(report)
            created += 1
            print(f"  Created: {title[:60]} (task={task_id or 'orphan'})")

        db.session.commit()
        print(f"\nDone: created {created} Report records")


if __name__ == '__main__':
    main()
