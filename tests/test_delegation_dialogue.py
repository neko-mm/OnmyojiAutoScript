import ast
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from test_delegation_reward import RewardTask, Timer, TooManyClicks


ROOT = Path(__file__).resolve().parents[1]


class TaskEnd(Exception):
    pass


def load_methods():
    source = ROOT / 'tasks/Delegation/script_task.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    task = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    methods = [node for node in task.body if isinstance(node, ast.FunctionDef)
               and node.name in ('run', '_advance_reward_dialogue', 'check_reward')]
    scope = {'Timer': Timer, 'GameTooManyClickError': TooManyClicks,
             'TaskEnd': TaskEnd, 'page_delegation': 'delegation',
             'logger': SimpleNamespace(info=lambda *_: None)}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), scope)
    return scope


class DialogueTask(RewardTask):
    I_REWARDS_IBUKI_DIALOGUE = 'IBUKI_DIALOGUE'
    C_REWARDS_DIALOGUE_CONTINUE = 'DIALOGUE_CONTINUE'

    def __init__(self, pages=3):
        super().__init__([])
        self.pages = pages
        self.actions = []
        self.closers = []
        self.navigator = SimpleNamespace(
            add_unknown_closer=lambda *actions: self.closers.extend(actions))
        self.config = SimpleNamespace(delegation=SimpleNamespace(
            delegation_config=SimpleNamespace(
                miyoshino_painting=False, bird_feather=False, find_earring=False,
                cat_boss=False, miyoshino=False, strange_trace=False)))
        for name, method in load_methods().items():
            if name in ('run', '_advance_reward_dialogue', 'check_reward'):
                setattr(self, name, method.__get__(self))

    def appear_then_click(self, target, interval, action=None):
        if target == self.I_REWARDS_IBUKI_DIALOGUE:
            if not self.pages:
                return False
            self.device.click(target)
            self.actions.append((target, action, interval))
            self.pages -= 1
            return True
        return super().appear_then_click(target, interval)

    def goto_page(self, destination):
        for _ in range(10):
            if not self.pages:
                self.actions.append(('arrived', destination))
                return
            if not any(closer() for closer in self.closers):
                raise RuntimeError('无法识别当前游戏页面：委派对话尚未关闭')
        raise RuntimeError('对话未结束')

    def set_next_run(self, **kwargs):
        self.actions.append(('scheduled', kwargs))


class DelegationDialogueTest(unittest.TestCase):
    def test_starting_in_dialogue_recovers_before_arrival(self):
        task = DialogueTask()
        with self.assertRaises(TaskEnd):
            task.run()
        self.assertEqual(task.pages, 0)
        self.assertEqual(len(task.closers), 1)
        self.assertEqual(task.actions[3], ('arrived', 'delegation'))

    def test_normal_page_does_not_click_dialogue_area(self):
        task = DialogueTask(pages=0)
        with self.assertRaises(TaskEnd):
            task.run()
        self.assertFalse(any(action[0] == 'IBUKI_DIALOGUE' for action in task.actions))

    def test_dialogue_during_reward_collection_is_advanced(self):
        task = DialogueTask()
        task.check_reward()
        self.assertEqual(task.pages, 0)
        self.assertEqual(len(task.actions), 3)
        self.assertTrue(all(action[1] == 'DIALOGUE_CONTINUE' for action in task.actions))
        self.assertTrue(all(action[2] >= 1 for action in task.actions))

    def test_missing_marker_does_not_click(self):
        task = DialogueTask(pages=0)
        self.assertFalse(task._advance_reward_dialogue())
        self.assertFalse(task.actions)

    def test_stuck_dialogue_keeps_click_guard(self):
        task = DialogueTask(pages=20)
        with self.assertRaises(TooManyClicks):
            task.check_reward()

    def test_marker_is_only_the_small_nameplate(self):
        folder = ROOT / 'tasks/Delegation/rewards'
        rule = json.loads((folder / 'image.json').read_text())[0]
        image = (folder / rule['imageName']).read_bytes()
        self.assertEqual(struct.unpack('!II', image[16:24]), (84, 36))
        self.assertEqual(rule['roiFront'], '310,533,84,36')
        self.assertGreaterEqual(rule['threshold'], 0.85)

    def test_continue_click_stays_inside_dialogue_text_area(self):
        rules = json.loads((ROOT / 'tasks/Delegation/rewards/click.json').read_text())
        x, y, w, h = map(int, rules[0]['roiFront'].split(','))
        self.assertGreaterEqual(x, 420)
        self.assertLessEqual(x+w, 820)
        self.assertGreaterEqual(y, 615)
        self.assertLessEqual(y+h, 675)
        self.assertGreater(w, 1)
        self.assertGreater(h, 1)


if __name__ == '__main__':
    unittest.main()
