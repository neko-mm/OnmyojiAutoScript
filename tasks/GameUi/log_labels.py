"""仅用于日志展示的常见页面中文名称，不改变页面标识和识别逻辑。"""

PAGE_LOG_LABELS = {
    "page_main": "庭院",
    "page_exploration": "探索",
    "page_team": "组队",
    "page_courtyard_affairs": "庭院事务",
    "page_daily": "每日任务",
    "page_soul_zones": "御魂副本",
    "page_awake_zones": "觉醒副本",
    "page_hero_test": "英杰试炼",
    "page_battle_prepare": "战斗准备",
    "page_battle": "战斗中",
    "page_battle_result": "战斗结算",
    "page_reward": "奖励页面",
    "page_battle_team": "组队房间",
}


def page_log_label(name: str) -> str:
    """保留原始页面标识，便于定位日志。"""
    label = PAGE_LOG_LABELS.get(name)
    return f"{label}（{name}）" if label else name
