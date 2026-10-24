import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_delegation_reward import RewardTask, Timer, TooManyClicks


ROOT = Path(__file__).resolve().parents[1]


class Click:
    def __init__(self, roi_front, roi_back, name):
        self.roi_front = roi_front
        self.name = name


def load_methods():
    source = ROOT / 'tasks/Delegation/script_task.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    task = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    methods = [node for node in task.body if isinstance(node, ast.FunctionDef)
               and node.name in ('check_reward', '_click_completed_reward')]
    scope = {'Timer': Timer, 'GameTooManyClickError': TooManyClicks,
             'RuleClick': Click, 'logger': SimpleNamespace(info=lambda *args: None)}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), scope)
    return scope


class MapRewardTask(RewardTask):
    def __init__(self, markers=None):
        super().__init__([])
        rule = json.loads((ROOT / 'tasks/Delegation/rewards/ocr.json').read_text())[0]
        roi = tuple(map(int, rule['roiFront'].split(',')))
        self.O_D_DONE = SimpleNamespace(roi=roi, name='D_DONE',
                                       detect_and_ocr=self.detect_and_ocr)
        self.device.image = None
        self.markers = markers if markers is not None else [(154, 390, 57, 28, '完成')]
        self.claimed = False
        self.areas = []
        self.allow_click = True
        for name, method in load_methods().items():
            if name in ('check_reward', '_click_completed_reward'):
                setattr(self, name, method.__get__(self))

    def detect_and_ocr(self, image):
        if self.claimed:
            return []
        rx, ry, rw, rh = self.O_D_DONE.roi
        return [SimpleNamespace(ocr_text=text,
                                box=((x-rx, y-ry), (x+w-rx, y-ry),
                                     (x+w-rx, y+h-ry), (x-rx, y+h-ry)))
                for x, y, w, h, text in self.markers
                if rx <= x and ry <= y and x+w <= rx+rw and y+h <= ry+rh]

    def ocr_appear_click(self, target, interval):
        # 现场日志中的右侧横幅坐标；连续点击不会进入领奖页面。
        self.device.click(target.name)
        return True

    def click(self, target, interval):
        if not self.allow_click:
            return False
        self.device.click(target.name)
        self.areas.append(target.roi_front)
        self.claimed = True
        return True


class DelegationRewardEntryTest(unittest.TestCase):
    def test_map_completion_is_opened_instead_of_sidebar_banner(self):
        task = MapRewardTask()
        task.check_reward()
        self.assertTrue(task.claimed)
        self.assertEqual(len(task.areas), 1)
        x, y, w, h = task.areas[0]
        self.assertGreaterEqual(x, 140)
        self.assertLessEqual(x+w, 220)
        self.assertGreaterEqual(y, 320)
        self.assertLessEqual(y+h, 385)
        self.assertGreater(w, 1)
        self.assertGreater(h, 1)

    def test_sidebar_completion_is_outside_search_area(self):
        task = MapRewardTask([(996, 390, 57, 34, '完成')])
        task.check_reward()
        self.assertFalse(task.areas)

    def test_multiple_completions_choose_one_marker_not_their_midpoint(self):
        task = MapRewardTask([(500, 500, 50, 25, '完成'), (154, 390, 57, 28, '完成')])
        self.assertTrue(task._click_completed_reward())
        x, y, w, h = task.areas[0]
        self.assertLess(x+w, 220)
        self.assertLess(y+h, 390)

    def test_partial_keyword_is_not_completion(self):
        task = MapRewardTask([(154, 390, 57, 28, '完成中')])
        self.assertFalse(task._click_completed_reward())
        self.assertFalse(task.areas)

    def test_click_interval_does_not_report_an_action(self):
        task = MapRewardTask()
        task.allow_click = False
        self.assertFalse(task._click_completed_reward())
        self.assertFalse(task.claimed)

    def test_unresponsive_map_entry_still_triggers_click_guard(self):
        task = MapRewardTask()

        def stuck_click(target, interval):
            task.device.click(target.name)
            return True

        task.click = stuck_click
        with self.assertRaises(TooManyClicks):
            task.check_reward()

    def test_marker_near_top_edge_is_not_clicked_outside_map(self):
        task = MapRewardTask([(154, 110, 57, 28, '完成')])
        self.assertFalse(task._click_completed_reward())
        self.assertFalse(task.areas)

    def test_reward_dialog_is_handled_before_map_ocr(self):
        task = MapRewardTask()
        task.clicks.extend(['REWARDS_GET', 'REWARDS_DONE'])
        task.check_reward()
        self.assertFalse(task.clicks)
        self.assertTrue(task.claimed)


if __name__ == '__main__':
    unittest.main()
