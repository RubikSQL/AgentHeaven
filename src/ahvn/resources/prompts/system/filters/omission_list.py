from typing import List

OMISSION_LIST_LIMIT_DEFAULT = -1


def omission_list(items: List, limit: int = OMISSION_LIST_LIMIT_DEFAULT) -> List:
    """\
    Cuts down a list by omitting middle items if it exceeds the specified limit.

    Args:
        items (List): The list of items.
        limit (int): The maximum number of items to keep.
            If limit is non-positive, no omission will be applied. Default is -1.

    Returns:
        List: The possibly shortened list with an omission indicator in the middle.
    """
    if limit <= 0:
        return items
    n = len(items)
    if n <= limit + 1:
        return items
    bottom_cnt = limit // 2
    top_cnt = limit - bottom_cnt
    omitted_cnt = n - limit
    return items[:top_cnt] + [("OMISSION", omitted_cnt)] + (items[-bottom_cnt:] if bottom_cnt > 0 else [])
