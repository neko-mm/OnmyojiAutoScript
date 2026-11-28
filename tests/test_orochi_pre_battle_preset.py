import json
import re
from pathlib import Path
from types import SimpleNamespace
import unittest


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


def load_switch_method():
    """提取 switch_orochi_preset_before_battle 及其常量，避免引入重型运行时依赖。"""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    const_lines = [
        line for line in source.splitlines()
        if line.startswith("_PRESET_")
    ]
    start = source.index("    def switch_orochi_preset_before_battle(")
    end = source.index("    def run_leader(", start)
    method_src = "\n".join(line[4:] if line.startswith("    ") else line for line in source[start:end].splitlines())
    code = "\n".join(const_lines) + "\n\n" + method_src

    def fake_get_color(image, area):
        return image(area)

    def fake_color_similar(c1, c2, threshold=10):
        return all(abs(a - b) <= threshold for a, b in zip(c1, c2))

    scope = {
        "Timer": FakeTimer,
        "sleep": lambda *_: None,
        "get_color": fake_get_color,
        "color_similar": fake_color_similar,
        "logger": SimpleNamespace(info=lambda *_: None, warning=lambda *_: None),
    }
    exec(compile(code, str(SCRIPT_PATH), "exec"), scope)
    return scope["switch_orochi_preset_before_battle"]


class FakeDevice:
    def __init__(self, group_colors):
        self.clicks = []
        self.swipes = []
        self.group_colors = dict(group_colors)
        self.image = self._sample_color

    def _sample_color(self, area):
        y_mid = (area[1] + area[3]) // 2
        idx = round((y_mid - 184) / 51) + 1
        return self.group_colors.get(idx, (225.5, 209.2, 189.0))

    def click(self, x, y, control_name=""):
        self.clicks.append((x, y, control_name))
        if control_name.startswith("OROCHI_PRESET_GROUP_"):
            g = int(control_name.rsplit("_", 1)[-1])
            self.group_colors[g] = (249.0, 215.0, 156.0)

    def swipe(self, p1, p2):
        self.swipes.append((p1, p2))


class FakeOrochiTask:
    I_TEAM_PRESET = "I_TEAM_PRESET"
    I_PRESET_DEPLOY = "I_PRESET_DEPLOY"

    def __init__(self, preset_enable=True, preset_group=1, preset_team=1, has_new_ui=True):
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
        self.device = FakeDevice({1: (249.0, 215.0, 156.0)})

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
        res = load_switch_method()(task)
        self.assertFalse(res)
        self.assertEqual(task.device.clicks, [])
        self.assertEqual(task.marked, [])

    def test_fallback_when_new_entry_absent(self):
        task = FakeOrochiTask(preset_enable=True, preset_group=2, preset_team=3, has_new_ui=False)
        res = load_switch_method()(task)
        self.assertFalse(res)
        self.assertEqual(task.marked, [])

    def test_switch_group_and_team_within_visible_slots(self):
        task = FakeOrochiTask(preset_enable=True, preset_group=2, preset_team=3, has_new_ui=True)
        res = load_switch_method()(task)
        self.assertTrue(res)
        self.assertFalse(task.popup_open)
        self.assertEqual(task.device.swipes, [])
        self.assertEqual(
            [c[2] for c in task.device.clicks],
            ["OROCHI_PRESET_GROUP_2", "OROCHI_PRESET_TEAM_3"],
        )
        self.assertEqual(task.marked, [("orochi_神罚", "preset")])

    def test_switch_team_beyond_three_triggers_swipe(self):
        task = FakeOrochiTask(preset_enable=True, preset_group=1, preset_team=5, has_new_ui=True)
        res = load_switch_method()(task)
        self.assertTrue(res)
        self.assertEqual(len(task.device.swipes), 2)
        self.assertEqual(task.device.clicks[-1][2], "OROCHI_PRESET_TEAM_5")
        self.assertEqual(task.device.clicks[-1][1], 204 + 2 * 96)
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
