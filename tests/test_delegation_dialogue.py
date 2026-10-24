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
               and node.name in ('run', 'delegate_one', '_advance_reward_dialogue', '_handle_reward_screen',
                                 '_recover_reward_screen', 'check_reward')]
    scope = {'Timer': Timer, 'GameTooManyClickError': TooManyClicks,
             'TaskEnd': TaskEnd, 'page_delegation': 'delegation',
             'logger': SimpleNamespace(info=lambda *_: None, warning=lambda *_: None,
                                       hr=lambda *_: None)}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), scope)
    return scope


class DialogueTask(RewardTask):
    I_REWARDS_IBUKI_DIALOGUE = 'IBUKI_DIALOGUE'
    C_REWARDS_DIALOGUE_CONTINUE = 'DIALOGUE_CONTINUE'

    def __init__(self, pages=3, complete=False):
        super().__init__([])
        self.pages = pages
        self.complete = complete
        self.allow_complete_click = True
        self.actions = []
        self.closers = []
        self.navigator = SimpleNamespace(
            add_unknown_closer=lambda *actions: self.closers.extend(actions))
        self.config = SimpleNamespace(delegation=SimpleNamespace(
            delegation_config=SimpleNamespace(
                miyoshino_painting=False, bird_feather=False, find_earring=False,
                cat_boss=False, miyoshino=False, strange_trace=False)))
        for name, method in load_methods().items():
            if name in ('run', 'delegate_one', '_advance_reward_dialogue', '_handle_reward_screen',
                        '_recover_reward_screen', 'check_reward'):
                setattr(self, name, method.__get__(self))

    def appear_then_click(self, target, interval, action=None):
        if target == self.I_REWARDS_DONE and self.complete:
            if not self.allow_complete_click:
                return False
            self.device.click(target)
            self.actions.append((target, action, interval))
            self.complete = False
            self.pages = 0
            return True
        if target == self.I_REWARDS_IBUKI_DIALOGUE:
            if not self.pages:
                return False
            self.device.click(target)
            self.actions.append((target, action, interval))
            if not self.complete:
                self.pages -= 1
            return True
        return super().appear_then_click(target, interval)

    def appear(self, target):
        return target == self.I_REWARDS_DONE and self.complete or super().appear(target)

    def goto_page(self, destination):
        for _ in range(10):
            if not self.pages and not self.complete:
                self.actions.append(('arrived', destination))
                return
            if not any(closer() for closer in self.closers):
                raise RuntimeError('无法识别当前游戏页面：委派对话尚未关闭')
        raise RuntimeError('对话未结束')

    def set_next_run(self, **kwargs):
        self.actions.append(('scheduled', kwargs))


class SelectionTask(DialogueTask):
    I_D_START = 'START'
    I_D_BACK = 'BACK'
    I_D_SKIP = 'SKIP'
    I_D_CONFIRM = 'CONFIRM'
    I_REWARDS_PANEL_COLLAPSED = 'PANEL_COLLAPSED'

    def __init__(self):
        super().__init__(pages=0)
        self.O_D_NAME = SimpleNamespace(keyword='')
        self.selected = False
        self.panel_collapsed = False
        self.frames = 0

    def screenshot(self):
        self.frames += 1
        if self.frames > 40:
            raise RuntimeError('详情循环一直等待委派名称，没有处理对话')

    def ocr_appear(self, target):
        return not self.selected

    def ocr_appear_click(self, target, interval):
        if target is self.O_D_NAME:
            if self.selected:
                return False
            self.selected = True
            self.pages = 2
            self.actions.append(('select',))
            return True
        return False

    def appear(self, target):
        if target == self.I_REWARDS_MIN:
            return not self.pages and not self.complete and not self.panel_collapsed
        return super().appear(target)

    def appear_then_click(self, target, interval, action=None):
        if target == self.I_REWARDS_PANEL_COLLAPSED:
            if not self.panel_collapsed:
                return False
            self.panel_collapsed = False
            self.actions.append(('expand_list',))
            return True
        clicked = super().appear_then_click(target, interval, action)
        if clicked and target == self.I_REWARDS_IBUKI_DIALOGUE and self.pages == 0:
            self.complete = True
            self.pages = 1
        if clicked and target == self.I_REWARDS_DONE:
            self.panel_collapsed = True
        return clicked


class DispatchTask(SelectionTask):
    C_D_1, C_D_2, C_D_3, C_D_4, C_D_5 = 'SLOT1', 'SLOT2', 'SLOT3', 'SLOT4', 'SLOT5'
    I_D_SELECT_1, I_D_SELECT_2, I_D_SELECT_3, I_D_SELECT_4 = 'SLOT1', 'SLOT2', 'SLOT3', 'SLOT4'

    def __init__(self):
        super().__init__()
        self.confirm = False
        self.start = False
        self.slots = set()
        self.confirm_ready = True

    def appear(self, target):
        if target == self.I_D_CONFIRM:
            return self.confirm
        if target == self.I_D_START:
            return self.start
        if target in (self.I_D_SELECT_1, self.I_D_SELECT_2, self.I_D_SELECT_3, self.I_D_SELECT_4):
            return target in self.slots
        return super().appear(target)

    def appear_then_click(self, target, interval, action=None):
        if target == self.I_D_CONFIRM and self.confirm:
            if not self.confirm_ready:
                self.confirm_ready = True
                return False
            self.confirm = False
            self.start = True
            self.actions.append(('dispatch',))
            return True
        if target == self.I_D_START and self.start:
            self.start = False
            self.actions.append(('start',))
            return True
        # 复现最后一页伊吹对话结束后，切到神乐的派遣详情。
        clicked = DialogueTask.appear_then_click(self, target, interval, action)
        if clicked and target == self.I_REWARDS_IBUKI_DIALOGUE and self.pages == 0:
            self.confirm = True
            self.panel_collapsed = True
        return clicked

    def click(self, target, interval):
        if target == self.C_D_5:
            return False
        self.slots.add(target)
        return True


class DelegationDialogueTest(unittest.TestCase):
    def test_open_dialogue_then_dispatch_detail_continues_to_start(self):
        task = DispatchTask()
        task.delegate_one('猫老大')
        self.assertIn(('dispatch',), task.actions)
        self.assertIn(('start',), task.actions)
        self.assertEqual(len(task.slots), 4)
        self.assertNotIn(('expand_list',), task.actions)

    def test_dispatch_button_cooldown_does_not_fall_into_reward_recovery(self):
        task = DispatchTask()
        task.confirm = True
        task.confirm_ready = False
        task.pages = 1
        task.delegate_one('猫老大')
        self.assertIn(('start',), task.actions)
        self.assertFalse(any(action[0] == 'IBUKI_DIALOGUE' for action in task.actions))

    def test_collapsed_arrow_is_not_a_reward_dialogue_button(self):
        task = SelectionTask()
        task.panel_collapsed = True
        original_appear = task.appear
        task.appear = lambda target: target == task.I_REWARDS_CHAT or original_appear(target)
        original_click = task.appear_then_click
        def click_arrow(target, interval, action=None):
            if target == task.I_REWARDS_CHAT:
                task.device.click(target)
                task.panel_collapsed = not task.panel_collapsed
                return True
            return original_click(target, interval, action)
        task.appear_then_click = click_arrow
        task.check_reward()
        self.assertEqual(task.actions, [('expand_list',)])
        self.assertNotIn(task.I_REWARDS_CHAT, task.device.click_record)

    def test_dispatch_popup_stops_reward_collection_without_clicking_arrow(self):
        task = SelectionTask()
        task.pages = 1
        task.panel_collapsed = True
        original_appear = task.appear
        task.appear = lambda target: target in (task.I_D_CONFIRM, task.I_REWARDS_CHAT) or original_appear(target)
        task.check_reward()
        self.assertEqual(task.actions, [])
        self.assertEqual(task.pages, 1)

    def test_completed_task_selected_by_name_recovers_full_reward_flow(self):
        task = SelectionTask()
        self.assertFalse(task.delegate_one('猫老大'))
        self.assertFalse(task.pages)
        self.assertFalse(task.complete)
        self.assertFalse(task.panel_collapsed)
        self.assertEqual(sum(action[0] == 'select' for action in task.actions), 1)
        self.assertIn(('expand_list',), task.actions)
        self.assertTrue(any(action[0] == 'REWARDS_DONE' for action in task.actions))

    def test_collection_reopens_collapsed_list(self):
        task = SelectionTask()
        task.panel_collapsed = True
        task.check_reward()
        self.assertEqual(task.actions, [('expand_list',)])

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

    def test_completion_popup_takes_priority_during_navigation(self):
        task = DialogueTask(complete=True)
        with self.assertRaises(TaskEnd):
            task.run()
        self.assertEqual(task.actions[0][0], 'REWARDS_DONE')
        self.assertFalse(any(action[0] == 'IBUKI_DIALOGUE' for action in task.actions))

    def test_completion_popup_takes_priority_during_collection(self):
        task = DialogueTask(complete=True)
        task.check_reward()
        self.assertEqual(task.actions[0][0], 'REWARDS_DONE')
        self.assertFalse(task.complete)

    def test_completion_cooldown_does_not_fall_through_to_dialogue(self):
        task = DialogueTask(complete=True)
        task.allow_complete_click = False
        self.assertFalse(task._recover_reward_screen())
        self.assertFalse(task.actions)

    def test_reward_popup_does_not_require_nameplate(self):
        task = DialogueTask(pages=0, complete=True)
        with self.assertRaises(TaskEnd):
            task.run()
        self.assertEqual(task.actions[0][0], 'REWARDS_DONE')

    def test_recovery_reports_bool_without_a_second_click(self):
        task = DialogueTask(complete=True)
        self.assertIs(task._recover_reward_screen(), True)
        self.assertEqual(len(task.actions), 1)

    def test_other_reward_controls_take_priority_over_nameplate(self):
        for button in ('REWARDS_GET', 'REWARDS_FALSE', 'CHAT_1', 'CHAT_2'):
            with self.subTest(button=button):
                task = DialogueTask()
                task.clicks.append(button)
                self.assertEqual(task._handle_reward_screen(), button)
                self.assertEqual(task.pages, 3)
                self.assertFalse(task.actions)

    def test_marker_is_only_the_small_nameplate(self):
        folder = ROOT / 'tasks/Delegation/rewards'
        rule = next(rule for rule in json.loads((folder / 'image.json').read_text())
                    if rule['itemName'] == 'rewards_ibuki_dialogue')
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
