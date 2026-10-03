import json
from pathlib import Path


# OASX 未同步翻译表时，日志仍应能显示常见任务的中文名称。
DEFAULT_TASK_NAMES = {
    'Restart': '重启',
    'GotoMain': '返回庭院',
    'GlobalGame': '全局配置',
    'Orochi': '八岐大蛇',
    'Sougenbi': '业原火',
    'FallenSun': '日轮之陨',
    'EternitySea': '永生之海',
    'DailyTrifles': '每日琐事',
    'AreaBoss': '地域鬼王',
    'GoldYoukai': '金币妖怪',
    'ExperienceYoukai': '经验妖怪',
    'Nian': '年兽',
    'TalismanPass': '花合战',
    'DemonEncounter': '逢魔之时',
    'Pets': '小猫咪',
    'SoulsTidy': '御魂整理',
    'Delegation': '式神委派',
    'WantedQuests': '悬赏封印',
    'Tako': '石距',
    'BondlingFairyland': '契灵之境',
    'EvoZone': '觉醒副本',
    'GoryouRealm': '御灵之境',
    'Exploration': '探索',
    'KekkaiUtilize': '结界蹭卡',
    'KekkaiActivation': '结界挂卡',
    'RealmRaid': '个人突破',
    'RyouToppa': '寮突破',
    'CollectiveMissions': '集体任务',
    'Hunt': '狩猎战',
    'TrueOrochi': '真八岐大蛇',
    'RichMan': '大富翁',
    'Secret': '秘闻副本',
    'WeeklyTrifles': '每周琐事',
    'MysteryShop': '神秘商店',
    'Duel': '斗技',
    'ActivityShikigami': '当期爬塔',
    'MetaDemon': '超鬼王',
    'MemoryScrolls': '绘卷',
    'DemonRetreat': '首领退治',
    'DyeTrials': '灵染试炼',
    'HeroTest': '英杰试炼',
}


class Addition:
    @classmethod
    def load_additions(cls) -> dict:
        result = {}
        files: str = ['en-US', 'zh-CN']
        for file in files:
            file_path = Path.cwd() / 'assets' / 'i18n' / f'{file}.json'
            result[file] = {}
            if not file_path.exists():
                continue
            with open(str(file_path), 'r', encoding='utf-8') as f:
                result[file] = json.load(f)
        return result


class I18n(Addition):
    file_zh_cn = Path.cwd() / 'module' / 'config' / 'i18n' / 'zh-CN.json'

    @classmethod
    def trans_zh_cn(cls, text) -> str:
        cn_zh_data = cls.load_zh_cn()
        return cn_zh_data.get(text, DEFAULT_TASK_NAMES.get(text, text))

    @classmethod
    def save_zh_cn(cls, data) -> None:
        I18n.file_zh_cn.parent.mkdir(parents=True, exist_ok=True)
        with open(str(I18n.file_zh_cn), 'w', encoding='utf-8') as f:
            s = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=str)
            f.write(s)

    @classmethod
    def load_zh_cn(cls) -> dict:
        if not I18n.file_zh_cn.exists():
            return {}
        with open(str(I18n.file_zh_cn), 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == '__main__':
    print(I18n.load_zh_cn())
