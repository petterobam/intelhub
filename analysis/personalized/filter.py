"""Filter platform data items by user interest tags."""


def filter_items_by_tags(items: list, interest_tags: list, platforms: list = None) -> list:
    """Filter items from aggregated platform data by user tags and platforms.

    Args:
        items: list of dicts with at least 'title' and 'content' keys
        interest_tags: [{"type": "company", "value": "华为"}, ...]
        platforms: optional list of platform names to filter by, e.g. ["weibo", "zhihu"]

    Returns:
        Filtered items with added 'match_tags' field listing matched keywords
    """
    if not interest_tags and not platforms:
        return items

    keywords = [tag['value'].lower() for tag in (interest_tags or []) if tag.get('value')]
    platform_set = set(platforms) if platforms else None

    result = []
    for item in items:
        # Platform filter
        if platform_set:
            item_platform = item.get('_platform', '') or item.get('source', '')
            if item_platform not in platform_set:
                continue

        # Keyword matching
        if keywords:
            text = (
                (item.get('title', '') or '') + ' ' +
                (item.get('content', '') or '') + ' ' +
                (item.get('summary', '') or '')
            ).lower()
            matched = [kw for kw in keywords if kw in text]
            if not matched:
                continue
            item = {**item, 'match_tags': matched}
        else:
            item = {**item, 'match_tags': []}

        result.append(item)

    return result
