import math
from typing import List, Optional


# [1001, 1002, 1018, 1052, 1122] -> "10011002101810521122"
def id_list2str(id_list: list) -> str:
    return "".join([str(x) for x in id_list])


def id_str2list(id_str: str) -> list:
    return [int(id_str[x : x + 4]) for x in range(0, len(id_str), 4)]


def best_route(now_rank: int, limit: Optional[int] = 5) -> List[int]:
    r = []
    while now_rank > 1:
        if now_rank <= 11:
            now_rank = 1
        elif now_rank <= 70:
            now_rank -= 10
        else:
            now_rank = math.floor(now_rank * 0.85)
        r.append(now_rank)
    return r[:limit]
