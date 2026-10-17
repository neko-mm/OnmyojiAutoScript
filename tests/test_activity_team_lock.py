import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class GameStuckError(Exception):
    pass


class Timer:
    def __init__(self, seconds):
        self.checks = 0

    def start(self):
        return self

    def reached(self):
        self.checks += 1
        return self.checks >= 3


def load_lock_team():
    source = Path(__file__).resolve().parents[1] / 'tasks/ActivityShikigami/activities/normal.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'NormalClimbAct')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'lock_team')
    scope = {'Timer': Timer, 'GameStuckError': GameStuckError,
             'GeneralBattleConfig': object, 'logger': SimpleNamespace(info=lambda *_: None)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
    return scope['lock_team']


class ActivityTask:
    I_LOCK = 'boss_lock'
    I_UNLOCK = 'boss_unlock'
    I_AP_LOCK = 'pass_lock'
    I_AP_UNLOCK = 'pass_unlock'

    def __init__(self, state, climb_type='pass'):
        self.state = state
        self.climb_type = climb_type
        self.clicks = []

    def screenshot(self):
        pass

    def appear(self, rule):
        return rule == self.state

    def appear_then_click(self, rule, interval):
        if not self.appear(rule):
            return False
        self.clicks.append(rule)
        self.state = rule.removesuffix('unlock') + 'lock' if rule.endswith('unlock') else rule.removesuffix('lock') + 'unlock'
        return True


class ActivityTeamLockTest(unittest.TestCase):
    def test_already_locked_does_not_click(self):
        task = ActivityTask('pass_lock')
        load_lock_team()(task, SimpleNamespace(lock_team_enable=True))
        self.assertEqual(task.clicks, [])

    def test_unlock_to_lock(self):
        task = ActivityTask('pass_unlock')
        load_lock_team()(task, SimpleNamespace(lock_team_enable=True))
        self.assertEqual(task.state, 'pass_lock')
        self.assertEqual(task.clicks, ['pass_unlock'])

    def test_lock_to_unlock(self):
        task = ActivityTask('pass_lock')
        load_lock_team()(task, SimpleNamespace(lock_team_enable=False))
        self.assertEqual(task.state, 'pass_unlock')
        self.assertEqual(task.clicks, ['pass_lock'])

    def test_unrecognized_switch_stops_with_specific_error(self):
        task = ActivityTask('unknown')
        with self.assertRaisesRegex(GameStuckError, '无法确认活动阵容锁定状态'):
            load_lock_team()(task, SimpleNamespace(lock_team_enable=True))
        self.assertEqual(task.clicks, [])

    def test_boss_uses_its_own_switch_rules(self):
        task = ActivityTask('boss_unlock', climb_type='boss')
        load_lock_team()(task, SimpleNamespace(lock_team_enable=True))
        self.assertEqual(task.clicks, ['boss_unlock'])


if __name__ == '__main__':
    unittest.main()
