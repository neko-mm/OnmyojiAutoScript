import ast
from collections import Counter, deque
from pathlib import Path
import unittest


class TooManyClicks(Exception):
    pass


class Timer:
    def __init__(self, limit):
        self.idle = 0

    def start(self):
        return self

    def reset(self):
        self.idle = 0

    def reached(self):
        self.idle += 1
        return self.idle >= 3


def load_check_reward():
    source = Path(__file__).resolve().parents[1] / 'tasks/Delegation/script_task.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    script_task = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ScriptTask')
    method = next(node for node in script_task.body if isinstance(node, ast.FunctionDef) and node.name == 'check_reward')
    scope = {'Timer': Timer, 'GameTooManyClickError': TooManyClicks}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
    return scope['check_reward']


class Device:
    def __init__(self):
        self.click_record = deque(maxlen=30)

    def click(self, name):
        self.click_record.append(name)
        counts = Counter(self.click_record).most_common()
        if counts[0][1] >= 10 or len(counts) >= 2 and counts[0][1] >= 6 and counts[1][1] >= 6:
            raise TooManyClicks

    def click_record_remove(self, name):
        self.click_record = deque((item for item in self.click_record if item != name), maxlen=30)


class RewardTask:
    O_D_DONE = 'D_DONE'
    I_REWARDS_GET = 'REWARDS_GET'
    I_REWARDS_CHAT = 'REWARDS_CHAT'
    I_CHAT_1 = 'CHAT_1'
    I_CHAT_2 = 'CHAT_2'
    I_REWARDS_DONE = 'REWARDS_DONE'
    I_REWARDS_FALSE = 'REWARDS_FALSE'
    I_REWARDS_MIN = 'REWARDS_MIN'

    def __init__(self, clicks):
        self.clicks = deque(clicks)
        self.device = Device()

    def screenshot(self):
        pass

    def appear_then_click(self, target, interval):
        if self.clicks and self.clicks[0] == target:
            self.device.click(self.clicks.popleft())
            return True
        return False

    def appear(self, target):
        return target == self.I_REWARDS_MIN

    def ocr_appear_click(self, target, interval):
        if self.clicks and self.clicks[0] == target:
            self.device.click(self.clicks.popleft())
            return True
        return False


class DelegationRewardTest(unittest.TestCase):
    def test_reward_stage_change_does_not_trigger_two_button_guard(self):
        task = RewardTask(['D_DONE'] * 7 + ['REWARDS_CHAT'] * 6 + ['REWARDS_DONE'])
        load_check_reward()(task)
        self.assertFalse(task.clicks)

    def test_repeated_clicks_in_one_stage_still_stop(self):
        task = RewardTask(['REWARDS_CHAT'] * 10)
        with self.assertRaises(TooManyClicks):
            load_check_reward()(task)

    def test_alternating_stages_still_have_a_total_limit(self):
        task = RewardTask(['D_DONE', 'REWARDS_CHAT'] * 20)
        with self.assertRaises(TooManyClicks):
            load_check_reward()(task)


if __name__ == '__main__':
    unittest.main()
