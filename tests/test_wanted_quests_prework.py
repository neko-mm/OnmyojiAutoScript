import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UnknownPage(Exception):
    pass


class TaskEnd(Exception):
    pass


class Timer:
    def __init__(self, *_):
        self.ticks = 0
        self.active = False

    def start(self):
        self.active = True
        return self

    def started(self):
        return self.active

    def reached(self):
        self.ticks += 1
        return self.ticks >= 3


class Task:
    I_TRACE_DISABLE = 'tracked'
    I_TRACE_ENABLE = 'track'
    I_WQ_SEAL = 'seal'
    I_WQ_DONE = 'done'
    I_UI_BACK_RED = 'close'
    I_WQ_INVITE_1, I_WQ_INVITE_2, I_WQ_INVITE_3 = 'invite1', 'invite2', 'invite3'
    I_WQ_TRACE_ONE_CHECK_OPENED = 'detail'
    C_WQ_DETAIL_TRACE = 'detail_track'
    special_main = False

    def __init__(self, state='unknown', text=''):
        self.state = state
        self.text = text
        self.actions = []
        self.device = SimpleNamespace(image=None)
        self.config = SimpleNamespace(model=SimpleNamespace(wanted_quests=SimpleNamespace(
            wanted_quests_config=SimpleNamespace(unwanted_boss_names=''),
            switch_soul_config=SimpleNamespace(enable=False, enable_switch_by_name=False))))
        self.O_WQ_TRACK_STATE = SimpleNamespace(
            detect_and_ocr=lambda _: [SimpleNamespace(ocr_text=line) for line in self.text.splitlines()])
        tree = ast.parse((ROOT / 'tasks/WantedQuests/script_task.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('run', 'open_wq_info', 'pre_work', 'pre_work_cooperation_only',
                                  '_trace_button_state', '_untrace_current')]
        scope = {'Timer': Timer, 'GamePageUnknownError': UnknownPage,
                 'TaskEnd': TaskEnd,
                 'page_main': 'main', 'page_exploration': 'exploration',
                 'logger': SimpleNamespace(info=lambda *_: None)}
        exec(compile(ast.Module(body=methods, type_ignores=[]), '<wanted>', 'exec'), scope)
        for name in ('run', 'open_wq_info', 'pre_work', 'pre_work_cooperation_only',
                     '_trace_button_state', '_untrace_current'):
            if name in scope:
                setattr(self, name, scope[name].__get__(self))

    def screenshot(self):
        pass

    def goto_page(self, page):
        self.actions.append(page)

    def get_current_page(self):
        return 'main'

    def appear(self, target):
        return target == 'close' or target == self.state

    def appear_then_click(self, target, interval):
        if target != self.state:
            return False
        self.actions.append(target)
        self.state = 'tracked'
        return True

    def ui_click_until_disappear(self, target):
        self.actions.append(target)

    def get_config(self):
        return SimpleNamespace(cooperation_only=False)

    def next_run(self):
        self.actions.append('scheduled')

    def click(self, target, interval):
        self.actions.append(target)
        if target == self.C_WQ_DETAIL_TRACE:
            self.text = '追踪'
        return True


class WantedPreworkTest(unittest.TestCase):
    def test_updated_templates_fit_their_search_areas_and_source_coordinates(self):
        updated = {'trace_enable', 'trace_disable', 'goto_1', 'goto_2', 'goto_3', 'goto_4',
                   'wq_trace_one_check_opened', 'wqc_fire', 'wqse_fire', 'e_exploration_click'}
        for task in ('WantedQuests', 'Exploration'):
            for path in (ROOT / 'tasks' / task).rglob('*.json'):
                rules = json.loads(path.read_text())
                if not isinstance(rules, list):
                    continue
                for rule in rules:
                    if rule.get('itemName') not in updated:
                        continue
                    with self.subTest(item=rule['itemName']):
                        raw = (path.parent / rule['imageName']).read_bytes()
                        width = int.from_bytes(raw[16:20], 'big')
                        height = int.from_bytes(raw[20:24], 'big')
                        x, y, w, h = map(int, rule['roiFront'].split(','))
                        rx, ry, rw, rh = map(int, rule['roiBack'].split(','))
                        self.assertEqual((width, height), (w, h))
                        self.assertTrue(rx <= x and ry <= y and x+w <= rx+rw and y+h <= ry+rh)
                        self.assertTrue(0 <= rx < rx+rw <= 1280 and 0 <= ry < ry+rh <= 720)

    def test_run_does_not_reschedule_as_success_after_recognition_failure(self):
        task = Task()
        with self.assertRaises(UnknownPage):
            task.run()
        self.assertNotIn('scheduled', task.actions)

    def test_detail_header_opens_without_old_top_left_tracking_checkbox(self):
        self.assertTrue(Task('detail').open_wq_info())

    def test_cancel_tracking_uses_random_area_rule_and_waits_for_state_change(self):
        task = Task(text='取消\n追踪')
        task._untrace_current()
        self.assertEqual(task.actions, ['detail_track'])

    def test_unknown_cancel_tracking_state_stops_without_blind_clicks(self):
        task = Task()
        with self.assertRaises(UnknownPage):
            task._untrace_current()
        self.assertEqual(task.actions, [])

    def test_unknown_button_is_not_reported_as_completed(self):
        task = Task()
        with self.assertRaises(UnknownPage):
            task.pre_work()
        self.assertNotIn('close', task.actions)

    def test_cooperation_unknown_button_is_also_an_error(self):
        with self.assertRaises(UnknownPage):
            Task().pre_work_cooperation_only()

    def test_enabled_tracking_is_clicked_before_exploration(self):
        task = Task('track')
        self.assertTrue(task.pre_work())
        self.assertEqual(task.actions, ['main', 'track', 'close', 'exploration'])

    def test_new_cancel_tracking_text_confirms_success(self):
        task = Task(text='取消\n追踪')
        self.assertTrue(task.pre_work())
        self.assertIn('exploration', task.actions)

    def test_cooperation_without_invitations_still_exits_normally(self):
        self.assertFalse(Task('track').pre_work_cooperation_only())

    def test_only_exact_tracking_text_is_accepted(self):
        for text, expected in [('一键\n追踪', False), ('追踪', False),
                               ('取消追踪', True), ('消\n追踪', True), ('下次刷新', None), ('追踪奖励', None)]:
            with self.subTest(text=text):
                self.assertIs(Task(text=text)._trace_button_state(), expected)


if __name__ == '__main__':
    unittest.main()
