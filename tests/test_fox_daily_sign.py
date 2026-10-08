import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest


class Timer:
    def __init__(self, limit):
        pass

    def start(self):
        return self

    def reset(self):
        pass

    def reached(self):
        return False


def load_courtyard_affairs():
    source = Path(__file__).resolve().parents[1] / 'tasks/DailyTrifles/script_task.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    script_task = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ScriptTask')
    method = next(node for node in script_task.body if isinstance(node, ast.FunctionDef) and node.name == 'run_courtyard_affairs')
    logger = SimpleNamespace(hr=lambda *args: None, info=lambda *args: None, warning=lambda *args: None)
    scope = {'Timer': Timer, 'logger': logger, 'datetime': datetime,
             'page_main': 'main', 'page_courtyard_affairs': 'affairs'}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
    return scope['run_courtyard_affairs']


class CourtyardTask:
    I_ENTER_COURTYARD_AFFAIRS_FOX = 'fox_entry'
    I_ENTER_COURTYARD_AFFAIRS = 'normal_entry'
    I_CHECK_IN_DAILY = 'daily_tab'
    I_ENTER_DAILY = 'enter_daily'
    I_ONE_COMPLETE = 'one_complete'
    I_FOX_DAILY_SIGN = 'fox_sign'
    I_UI_BACK_RED = 'close'

    def __init__(self, fox, sign):
        self.fox = fox
        self.sign = sign
        self.actions = []
        self.config = SimpleNamespace(daily_trifles=SimpleNamespace(done_record=SimpleNamespace()))

    def goto_page(self, page):
        self.actions.append(('page', page))

    def screenshot(self):
        pass

    def appear(self, target, interval=None):
        return target in ('daily_tab', 'normal_entry') or target == 'fox_entry' and self.fox

    def appear_then_click(self, target, interval):
        if target == 'fox_sign' and not self.sign:
            return False
        self.actions.append(('click', target))
        return True

    def wait_until_appear(self, target, wait_time):
        return True


class FoxDailySignTest(unittest.TestCase):
    def test_fox_courtyard_opens_sign_after_one_complete(self):
        task = CourtyardTask(fox=True, sign=True)
        load_courtyard_affairs()(task)
        self.assertIn(('click', 'fox_sign'), task.actions)
        self.assertIn(('click', 'close'), task.actions)
        self.assertLess(task.actions.index(('click', 'one_complete')),
                        task.actions.index(('click', 'fox_sign')))

    def test_other_courtyard_does_not_click_fox_sign(self):
        task = CourtyardTask(fox=False, sign=True)
        load_courtyard_affairs()(task)
        self.assertNotIn(('click', 'fox_sign'), task.actions)

    def test_claimed_fox_sign_is_skipped(self):
        task = CourtyardTask(fox=True, sign=False)
        load_courtyard_affairs()(task)
        self.assertNotIn(('click', 'close'), task.actions)


if __name__ == '__main__':
    unittest.main()
