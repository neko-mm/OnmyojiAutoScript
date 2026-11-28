import json
import re
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tasks/Orochi/script_task.py"
ASSETS_PATH = ROOT / "tasks/Orochi/assets.py"
IMAGE_JSON_PATH = ROOT / "tasks/Orochi/o/image.json"


class FakeTimer:
    def __init__(self, seconds):
        self.limit = seconds
        self.ticks = 0

    def start(self):
        return self

    def current(self):
        return self.ticks * 0.6

    def reached(self):
        self.ticks += 1
        return self.ticks > 12


def load_switch_methods():
    """提取战前切队相关方法与常量，避免引入重型运行时依赖。"""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    const_lines = [
        line for line in source.splitlines()
        if line.startswith("_PRESET_")
    ]
    start = source.index("    @staticmethod\n    def _count_preset_slot_purple_pixels(")
    end = source.index("    def run_leader(", start)
    method_src = "\n".join(line[4:] if line.startswith("    ") else line for line in source[start:end].splitlines())
    method_src = method_src.replace("@staticmethod\n", "")
    code = "\n".join(const_lines) + "\n\n" + method_src

    def fake_get_color(image, area):
        x1, y1, x2, y2 = area
        patch = image[y1:y2, x1:x2]
        return tuple(float(v) for v in patch.mean(axis=(0, 1)))

    def fake_color_similar(c1, c2, threshold=10):
        diff = np.array(c1, dtype=int) - np.array(c2, dtype=int)
        dist = int(np.max(np.maximum(diff, 0)) - np.min(np.minimum(diff, 0)))
        return dist <= threshold

    scope = {
        "np": np,
        "Timer": FakeTimer,
        "sleep": lambda *_: None,
        "get_color": fake_get_color,
        "color_similar": fake_color_similar,
        "logger": SimpleNamespace(info=lambda *_: None, warning=lambda *_: None),
    }
    exec(compile(code, str(SCRIPT_PATH), "exec"), scope)
    return scope["_count_preset_slot_purple_pixels"], scope["switch_orochi_preset_before_battle"]


class FakeDevice:
    def __init__(self, selected_group=1, selected_slot=0, unselected_rgb=(218, 200, 180)):
        self.clicks = []
        self.swipes = []
        self.selected_group = selected_group
        self.selected_slot = selected_slot
        self.unselected_rgb = unselected_rgb
        self.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self._render()

    def _render(self):
        self.image[:, :] = (30, 30, 30)
        for g in range(1, 8):
            y = 184 + (g - 1) * 51
            rgb = (249, 215, 156) if g == self.selected_group else self.unselected_rgb
            self.image[y - 6:y + 7, 415:435] = rgb
        if self.selected_slot is not None:
            y_top = 158 + self.selected_slot * 96
            self.image[y_top + 15:y_top + 75, 535:543] = (140, 50, 220)
            self.image[y_top + 15:y_top + 75, 918:926] = (140, 50, 220)

    def click(self, x, y, control_name=""):
        self.clicks.append((x, y, control_name))
        if control_name.startswith("OROCHI_PRESET_GROUP_"):
            self.selected_group = int(control_name.rsplit("_", 1)[-1])
            self.selected_slot = 0  # 切分组后重置当前选中槽位
            self._render()
        elif control_name.startswith("OROCHI_PRESET_TEAM_"):
            slot = round((y - (158 + 16)) / 96)
            self.selected_slot = slot
            self._render()

    def swipe(self, p1, p2):
        self.swipes.append((p1, p2))


class FakeOrochiTask:
    I_TEAM_PRESET = "I_TEAM_PRESET"
    I_PRESET_DEPLOY = "I_PRESET_DEPLOY"

    def __init__(self, preset_enable=True, preset_group=1, preset_team=1, has_new_ui=True, unselected_rgb=(218, 200, 180)):
        self.config = SimpleNamespace(
            orochi=SimpleNamespace(
                orochi_config=SimpleNamespace(layer="神罚"),
                general_battle_config=SimpleNamespace(
                    preset_enable=preset_enable,
                    preset_group=preset_group,
                    preset_team=preset_team,
                    lock_team_enable=True,
                ),
            )
        )
        self.has_new_ui = has_new_ui
        self.popup_open = False
        self.marked = []
        self.device = FakeDevice(selected_group=1, selected_slot=0, unselected_rgb=unselected_rgb)
        self._count_fn, self._switch_fn = load_switch_methods()

    def _count_preset_slot_purple_pixels(self, image, slot_index):
        return self._count_fn(image, slot_index)

    def _orochi_battle_key(self):
        return f"orochi_{self.config.orochi.orochi_config.layer}"

    def screenshot(self):
        pass

    def appear(self, rule):
        if rule == self.I_TEAM_PRESET:
            return self.has_new_ui
        if rule == self.I_PRESET_DEPLOY:
            return self.popup_open
        return False

    def appear_then_click(self, rule, interval=1):
        if not self.appear(rule):
            return False
        if rule == self.I_TEAM_PRESET:
            self.popup_open = True
            return True
        if rule == self.I_PRESET_DEPLOY:
            self.popup_open = False
            return True
        return False

    def mark_battle_behavior_done(self, battle_key, behavior_name):
        self.marked.append((battle_key, behavior_name))


class OrochiPreBattlePresetTest(unittest.TestCase):
    def test_disabled_preset_skips_immediately(self):
        task = FakeOrochiTask(preset_enable=False)
        res = task._switch_fn(task)
        self.assertFalse(res)
        self.assertEqual(task.device.clicks, [])
        self.assertEqual(task.marked, [])

    def test_fallback_when_new_entry_absent(self):
        task = FakeOrochiTask(preset_enable=True, preset_group=2, preset_team=3, has_new_ui=False)
        res = task._switch_fn(task)
        self.assertFalse(res)
        self.assertEqual(task.marked, [])

    def test_switch_group_2_team_3_even_with_color_shift(self):
        # 模拟未选中色与标准图有明显色偏，仍必须点击分组 2 并校验队伍 3 紫色选中框
        task = FakeOrochiTask(
            preset_enable=True,
            preset_group=2,
            preset_team=3,
            has_new_ui=True,
            unselected_rgb=(210, 195, 175),
        )
        res = task._switch_fn(task)
        self.assertTrue(res)
        self.assertFalse(task.popup_open)
        self.assertEqual(task.device.selected_group, 2)
        self.assertEqual(task.device.selected_slot, 2)
        self.assertEqual(task.device.swipes, [])
        self.assertEqual(
            [c[2] for c in task.device.clicks],
            ["OROCHI_PRESET_GROUP_2", "OROCHI_PRESET_TEAM_3"],
        )
        # 验证点击落在第 3 张卡片标题栏 (680, 366)
        self.assertEqual(task.device.clicks[-1][:2], (680, 366))
        self.assertEqual(task.marked, [("orochi_神罚", "preset")])

    def test_switch_team_beyond_three_triggers_swipe(self):
        task = FakeOrochiTask(preset_enable=True, preset_group=1, preset_team=5, has_new_ui=True)
        res = task._switch_fn(task)
        self.assertTrue(res)
        self.assertEqual(len(task.device.swipes), 2)
        self.assertEqual(task.device.clicks[-1], (680, 366, "OROCHI_PRESET_TEAM_5"))
        self.assertEqual(task.marked, [("orochi_神罚", "preset")])

    def test_wired_into_alone_leader_and_wild(self):
        src = SCRIPT_PATH.read_text(encoding="utf-8")
        for fn in ("run_leader", "run_alone", "run_wild"):
            m = re.search(rf"def {fn}\(self\):.*?(?=\n    def |\Z)", src, re.S)
            self.assertIsNotNone(m, f"missing {fn}")
            self.assertIn("self.switch_orochi_preset_before_battle()", m.group(0), f"{fn} 未调用战前切队")

    def test_assets_and_image_json_consistent(self):
        items = {x["itemName"]: x for x in json.loads(IMAGE_JSON_PATH.read_text(encoding="utf-8"))}
        self.assertIn("team_preset", items)
        self.assertIn("preset_deploy", items)
        for key in ("team_preset", "preset_deploy"):
            img_file = ROOT / "tasks/Orochi/o" / items[key]["imageName"]
            self.assertTrue(img_file.exists(), f"missing {img_file}")
        assets_src = ASSETS_PATH.read_text(encoding="utf-8")
        self.assertIn("I_TEAM_PRESET = RuleImage(", assets_src)
        self.assertIn("I_PRESET_DEPLOY = RuleImage(", assets_src)


if __name__ == "__main__":
    unittest.main()
