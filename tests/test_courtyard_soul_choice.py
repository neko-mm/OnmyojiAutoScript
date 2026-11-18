import ast
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIORITY = ('招财猫', '火灵', '蚌精', '共潜', '薙魂', '返魂香', '木魅', '狂骨',
            '针女', '破势', '网切', '海月火玉', '鸣屋', '荒骷髅', '魅妖',
            '魍魉之匣', '雪幽魂', '钟灵')


class UnknownPage(Exception):
    pass


class Timer:
    def __init__(self, limit):
        self.limit = limit
        self.elapsed = 0

    def start(self):
        return self

    def reset(self):
        self.elapsed = 0

    def reached(self):
        self.elapsed += 0.5
        return self.elapsed >= self.limit


def load_methods():
    path = ROOT / 'tasks/DailyTrifles/script_task.py'
    cls = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef))
    names = ('run_courtyard_affairs', '_handle_courtyard_soul_choice',
             '_complete_courtyard_affairs', '_finish_fox_daily_sign',
             '_handle_daily_sign_popup', '_background_brightness', '_background_is_clear')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    scope = dict(Timer=Timer, datetime=datetime, GamePageUnknownError=UnknownPage,
                 COURTYARD_SOUL_PRIORITY=PRIORITY, page_main='main',
                 page_courtyard_affairs='affairs',
                 logger=SimpleNamespace(hr=lambda *_: None, info=lambda *_: None,
                                        warning=lambda *_: None))
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), 'exec'), scope)
    return {name: scope[name] for name in names if name in scope}


class Frame:
    def __init__(self, task):
        self.task = task

    def __getitem__(self, _):
        return SimpleNamespace(mean=lambda: 100 if self.task.state in ('main', 'daily') else 45)


class CourtyardTask:
    I_ENTER_COURTYARD_AFFAIRS_FOX = 'fox_entry'
    I_ENTER_COURTYARD_AFFAIRS = 'normal_entry'
    I_CHECK_IN_DAILY = 'daily_tab'
    I_ENTER_DAILY = 'enter_daily'
    I_ONE_COMPLETE = 'one_complete'
    I_FOX_DAILY_SIGN = 'fox_sign'
    I_UI_BACK_RED = 'close'
    I_UI_CONFIRM = 'confirm'
    I_UI_CONFIRM_SAMLL = 'small_confirm'
    I_COURTYARD_SOUL_TITLE = 'soul_title'
    I_COURTYARD_SOUL_SELECT_1, I_COURTYARD_SOUL_SELECT_2, I_COURTYARD_SOUL_SELECT_3 = 'select1', 'select2', 'select3'
    C_COURTYARD_SOUL_1, C_COURTYARD_SOUL_2, C_COURTYARD_SOUL_3 = 'choose1', 'choose2', 'choose3'
    I_DAILY_SIGN_DRAW = 'draw_sign'
    C_DAILY_SIGN_DRAW = 'draw_area'
    I_DAILY_SIGN_RESULT = 'sign_result'
    I_DAILY_SIGN_RESULT_CLOSE = 'sign_result_close'
    C_DAILY_SIGN_CLOSE = 'sign_close_area'
    I_COURTYARD_CLAIM_SUCCESS = 'claim_success'
    C_COURTYARD_CLAIM_CLOSE = 'claim_close_area'

    def __init__(self, fox=True, sign=True, has_choice=True):
        self.fox, self.sign, self.has_choice = fox, sign, has_choice
        self.state = 'main'
        self.enabled = True
        self.actions = []
        self.frames = 0
        self.names = ['恶楼', '雪幽魂', '隐念']
        self.buttons = True
        self.allow_choice = True
        self.require_confirm = True
        self.sign_stuck = False
        self.complete_stuck = False
        self.auto_sign = False
        self.auto_sign_needs_draw = False
        self.new_sign_result = False
        self.sign_has_close_button = False
        self.result_stuck = False
        self.receipt_stuck = False
        self.receipt_goes_main = False
        self.device = SimpleNamespace(image=Frame(self))
        self.config = SimpleNamespace(daily_trifles=SimpleNamespace(
            done_record=SimpleNamespace(courtyard_affairs_dt=None)))
        for index in range(3):
            setattr(self, f'O_COURTYARD_SOUL_{index+1}', SimpleNamespace(
                ocr=lambda _, index=index: self.names[index]))
        for name, method in load_methods().items():
            setattr(self, name, method.__get__(self))

    def screenshot(self):
        self.frames += 1
        if self.frames > 200:
            raise RuntimeError('庭院事务循环未退出')

    def goto_page(self, page):
        if self.state not in ('main', 'daily'):
            raise AssertionError('尚有弹窗，不能直接退出庭院事务或继续下个任务')
        self.actions.append(('page', page))
        self.state = 'daily' if page == 'affairs' else 'main'

    def get_current_page(self):
        return 'affairs' if self.state == 'daily' else 'main'

    def appear(self, target, interval=None):
        if target in ('normal_entry', 'fox_entry'):
            return self.state == 'main' and (target == 'normal_entry' or self.fox)
        if target == 'daily_tab':
            return self.state == 'daily'
        if target == 'one_complete':
            return self.state == 'daily'
        if target == 'soul_title':
            return self.state == 'choice'
        if target in ('select1', 'select2', 'select3'):
            return self.state == 'choice' and self.buttons
        if target == 'fox_sign':
            return self.state == 'main' and self.fox and self.sign
        if target == 'sign_result':
            return self.state == 'result' and (self.auto_sign or self.new_sign_result)
        if target == 'sign_result_close':
            return self.state == 'result' and self.sign_has_close_button
        if target == 'claim_success':
            return self.auto_sign and self.state in ('result', 'receipt')
        return (target, self.state) in (('confirm', 'confirm'), ('draw_sign', 'drum'), ('close', 'result'))

    def appear_then_click(self, target, interval=None, action=None):
        if not self.appear(target):
            return False
        self.actions.append(('click', target))
        if target == 'one_complete' and not self.complete_stuck:
            self.state = 'choice' if self.has_choice else 'reward'
        elif target == 'confirm':
            self.state = 'reward'
        elif target == 'fox_sign':
            self.state = 'drum'
        elif target == 'draw_sign':
            self.state = 'unknown' if self.sign_stuck else 'result'
        elif target == 'close':
            self.state, self.sign = 'main', False
        elif target == 'sign_result' and not self.sign_has_close_button and not self.result_stuck:
            self.state, self.sign = ('receipt' if self.auto_sign else 'main'), False
        elif target == 'claim_success' and not self.receipt_stuck:
            self.state, self.enabled = ('main' if self.receipt_goes_main else 'daily'), False
        return True

    def click(self, target, interval=None):
        if target == 'sign_result_close':
            self.actions.append(('click', target))
            if not self.result_stuck:
                self.state, self.sign = ('receipt' if self.auto_sign else 'main'), False
            return True
        if not self.allow_choice:
            return False
        self.actions.append(('click', target))
        self.state = ('drum' if self.auto_sign_needs_draw else 'result') if self.auto_sign else \
            ('confirm' if self.require_confirm else 'reward')
        return True

    def ui_reward_appear_click(self):
        if self.state != 'reward':
            return False
        self.actions.append(('click', 'reward'))
        self.state, self.enabled = 'daily', False
        return True

    def _one_complete_enabled(self):
        return self.enabled

    def wait_until_appear(self, target, wait_time):
        return self.appear(target)


class CourtyardSoulChoiceTest(unittest.TestCase):
    def test_sign_close_button_takes_priority_when_empty_area_does_not_work(self):
        task = CourtyardTask()
        task.auto_sign = task.sign_has_close_button = True
        task.run_courtyard_affairs()
        self.assertLess(task.actions.index(('click', 'sign_result_close')),
                        task.actions.index(('click', 'claim_success')))
        self.assertNotIn(('click', 'sign_result'), task.actions)

    def test_close_button_alone_does_not_identify_sign_result(self):
        task = CourtyardTask()
        task.state, task.sign_has_close_button = 'result', True
        self.assertFalse(task._handle_daily_sign_popup())
        self.assertEqual(task.actions, [])

    def test_automatic_sign_drum_is_also_handled_before_courtyard_exit(self):
        task = CourtyardTask()
        task.auto_sign = task.auto_sign_needs_draw = True
        task.run_courtyard_affairs()
        self.assertIn(('click', 'draw_sign'), task.actions)
        self.assertIn(('click', 'sign_result'), task.actions)
        self.assertIn(('click', 'claim_success'), task.actions)

    def test_unrelated_page_does_not_trigger_sign_popup_clicks(self):
        task = CourtyardTask()
        task.state = 'daily'
        self.assertFalse(task._handle_daily_sign_popup())
        self.assertEqual(task.actions, [])

    def test_automatic_sign_result_is_closed_inside_courtyard_completion(self):
        task = CourtyardTask()
        task.auto_sign = True
        task.run_courtyard_affairs()
        self.assertIsNotNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)
        self.assertIn(('click', 'choose2'), task.actions)
        self.assertLess(task.actions.index(('click', 'sign_result')),
                        task.actions.index(('click', 'claim_success')))
        self.assertNotIn(('click', 'fox_sign'), task.actions)

    def test_claim_success_may_return_directly_to_main(self):
        task = CourtyardTask()
        task.auto_sign = task.receipt_goes_main = True
        task.run_courtyard_affairs()
        self.assertEqual(task.state, 'main')
        self.assertIsNotNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)

    def test_covered_claim_success_is_not_clicked_before_the_sign_result(self):
        task = CourtyardTask()
        task.auto_sign, task.result_stuck = True, True
        with self.assertRaises(UnknownPage):
            task.run_courtyard_affairs()
        self.assertNotIn(('click', 'claim_success'), task.actions)
        self.assertIsNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)

    def test_stuck_receipt_does_not_mark_affairs_complete(self):
        task = CourtyardTask()
        task.auto_sign, task.receipt_stuck = True, True
        with self.assertRaises(UnknownPage):
            task.run_courtyard_affairs()
        self.assertIsNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)

    def test_new_result_popup_is_also_closed_after_clicking_the_sign_drum(self):
        task = CourtyardTask()
        task.new_sign_result = True
        task.run_courtyard_affairs()
        self.assertIn(('click', 'draw_sign'), task.actions)
        self.assertIn(('click', 'sign_result'), task.actions)

    def test_priority_matches_the_agreed_order(self):
        tree = ast.parse((ROOT / 'tasks/DailyTrifles/config.py').read_text())
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'COURTYARD_SOUL_PRIORITY'
                                  for t in n.targets))
        self.assertEqual(ast.literal_eval(assignment.value), PRIORITY)

    def test_soul_selection_and_sign_are_finished_before_marking_done(self):
        task = CourtyardTask()
        task.run_courtyard_affairs()
        self.assertEqual(task.state, 'main')
        self.assertIn(('click', 'choose2'), task.actions)
        self.assertIn(('click', 'draw_sign'), task.actions)
        self.assertIn(('click', 'close'), task.actions)
        self.assertIsNotNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)

    def test_priority_uses_names_not_positions(self):
        for names, expected in [(['针女', '招财猫', '狂骨'], 'choose2'),
                                (['木魅', '蚌精', '火灵'], 'choose3'),
                                (['共潜', '返魂香', '薙魂'], 'choose1')]:
            with self.subTest(names=names):
                task = CourtyardTask()
                task.state, task.names = 'choice', names
                self.assertTrue(task._handle_courtyard_soul_choice())
                self.assertEqual(task.actions[-1], ('click', expected))

    def test_unknown_names_fall_back_to_leftmost(self):
        task = CourtyardTask()
        task.state, task.names = 'choice', ['恶楼', '隐念', '遗念火']
        self.assertTrue(task._handle_courtyard_soul_choice())
        self.assertEqual(task.actions[-1], ('click', 'choose1'))

    def test_missing_name_is_retried_without_clicking(self):
        task = CourtyardTask()
        task.state, task.names = 'choice', ['招财猫', '', '针女']
        self.assertTrue(task._handle_courtyard_soul_choice())
        self.assertEqual(task.actions, [])

    def test_ocr_edge_punctuation_is_not_treated_as_part_of_the_soul_name(self):
        task = CourtyardTask()
        task.state, task.names = 'choice', ['。招财猫', '雪 幽魂', '隐念']
        task._handle_courtyard_soul_choice()
        self.assertEqual(task.actions[-1], ('click', 'choose1'))

    def test_click_cooldown_does_not_claim_a_selection_was_made(self):
        task = CourtyardTask()
        task.state, task.allow_choice = 'choice', False
        self.assertTrue(task._handle_courtyard_soul_choice())
        self.assertFalse(getattr(task, '_courtyard_soul_pending', False))

    def test_no_confirmation_popup_is_also_supported(self):
        task = CourtyardTask()
        task.require_confirm = False
        task.run_courtyard_affairs()
        self.assertIsNotNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)
        self.assertNotIn(('click', 'confirm'), task.actions)

    def test_already_finished_affairs_do_not_click_one_complete(self):
        task = CourtyardTask(sign=False)
        task.enabled = False
        task.run_courtyard_affairs()
        self.assertNotIn(('click', 'one_complete'), task.actions)
        self.assertIsNotNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)

    def test_soul_button_areas_are_random_click_regions_not_single_pixels(self):
        rules = json.loads((ROOT / 'tasks/DailyTrifles/dt/click.json').read_text())
        for rule in rules:
            if not rule['itemName'].startswith('courtyard_soul_'):
                continue
            x, y, w, h = map(int, rule['roiFront'].split(','))
            self.assertGreater(w, 1)
            self.assertGreater(h, 1)
            self.assertTrue(180 <= x < x+w <= 1105)
            self.assertTrue(555 <= y < y+h <= 620)

    def test_new_templates_fit_the_source_and_search_rectangles(self):
        folder = ROOT / 'tasks/DailyTrifles/dt'
        rules = json.loads((folder / 'image_courtyard_affairs.json').read_text())
        for rule in rules:
            if not (rule['itemName'].startswith('courtyard_soul_') or rule['itemName'] in
                    ('daily_sign_draw', 'daily_sign_result', 'daily_sign_result_close',
                     'courtyard_claim_success')):
                continue
            with self.subTest(rule=rule['itemName']):
                raw = (folder / rule['imageName']).read_bytes()
                w, h = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
                x, y, fw, fh = map(int, rule['roiFront'].split(','))
                rx, ry, rw, rh = map(int, rule['roiBack'].split(','))
                self.assertEqual((w, h), (fw, fh))
                self.assertTrue(0 <= rx <= x and 0 <= ry <= y)
                self.assertTrue(x+w <= rx+rw <= 1280 and y+h <= ry+rh <= 720)

    def test_missing_button_is_not_clicked(self):
        task = CourtyardTask()
        task.state, task.buttons = 'choice', False
        self.assertTrue(task._handle_courtyard_soul_choice())
        self.assertEqual(task.actions, [])

    def test_no_title_means_no_soul_clicks(self):
        task = CourtyardTask()
        self.assertFalse(task._handle_courtyard_soul_choice())
        self.assertEqual(task.actions, [])

    def test_choice_popup_disappearance_is_not_completion(self):
        task = CourtyardTask()
        task.allow_choice = False
        with self.assertRaises(UnknownPage):
            task.run_courtyard_affairs()
        self.assertEqual(task.state, 'choice')
        self.assertIsNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)

    def test_unhandled_sign_blocks_following_tasks_and_done_record(self):
        task = CourtyardTask()
        task.sign_stuck = True
        with self.assertRaises(UnknownPage):
            task.run_courtyard_affairs()
        self.assertIsNone(task.config.daily_trifles.done_record.courtyard_affairs_dt)

    def test_normal_courtyard_does_not_open_fox_sign(self):
        task = CourtyardTask(fox=False, has_choice=False)
        task.run_courtyard_affairs()
        self.assertNotIn(('click', 'fox_sign'), task.actions)

    def test_already_claimed_sign_is_skipped(self):
        task = CourtyardTask(sign=False, has_choice=False)
        task.run_courtyard_affairs()
        self.assertNotIn(('click', 'fox_sign'), task.actions)


if __name__ == '__main__':
    unittest.main()
