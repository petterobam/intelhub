"""Seed rss_sources table from anyfeeder OPML feed.

Usage:
    python scripts/seed_rss_sources.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xml.etree.ElementTree as ET
import urllib.request

OPML_URL = 'https://plink.anyfeeder.com/feeds-all.opml'


def fetch_opml(url=OPML_URL):
    """Fetch OPML XML from URL."""
    req = urllib.request.Request(url, headers={'User-Agent': 'IntelHub/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8')


def parse_opml(xml_text):
    """Parse OPML XML, return list of (category, name, url)."""
    root = ET.fromstring(xml_text)
    results = []
    for body in root.findall('body'):
        for outline in body.findall('outline'):
            cat = outline.get('text') or outline.get('title') or '其他'
            # Check if this outline has children (category container)
            children = outline.findall('outline')
            if children:
                for child in children:
                    name = child.get('text') or child.get('title') or ''
                    url = child.get('xmlUrl') or ''
                    if name and url:
                        results.append((cat, name, url))
            else:
                # Direct feed entry (no children)
                url = outline.get('xmlUrl') or ''
                if url:
                    name = outline.get('text') or outline.get('title') or cat
                    results.append(('其他', name, url))
    return results


def seed_from_url(url=OPML_URL):
    """Fetch OPML and seed the database. Returns count of new sources."""
    from app import create_app, db
    from app.models.rss_source import RssSource

    app = create_app()
    with app.app_context():
        xml_text = fetch_opml(url)
        items = parse_opml(xml_text)
        added = 0
        for cat, name, feed_url in items:
            exists = RssSource.query.filter_by(url=feed_url).first()
            if not exists:
                slug = RssSource.make_unique_slug(name, feed_url)
                src = RssSource(name=name, slug=slug, url=feed_url, category=cat)
                db.session.add(src)
                added += 1
        db.session.commit()
        print(f"Imported {added} new RSS sources ({len(items)} total in OPML)")
        return added


if __name__ == '__main__':
    seed_from_url()
