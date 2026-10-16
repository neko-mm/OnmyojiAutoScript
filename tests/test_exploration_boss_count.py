import ast
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import unittest


source = Path(__file__).resolve().parents[1] / 'tasks/Exploration'


def load_method(filename, class_name, method_name):
    tree = ast.parse((source / filename).read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    scope = {
        'datetime': datetime,
        'pages': SimpleNamespace(Page=object, page_exp_main='exp_main'),
        'UserStatus': SimpleNamespace(MEMBER='member'),
        'logger': SimpleNamespace(info=lambda *_: None),
    }
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source / filename), 'exec'), scope)
    return scope[method_name]


class ExplorationBossCountTest(unittest.TestCase):
    def make_task(self, boss_target, boss_count, battles):
        task = SimpleNamespace(
            current_count=battles,
            boss_count=boss_count,
            _config=SimpleNamespace(
                exploration_config=SimpleNamespace(minions_cnt=30, boss_cnt=boss_target),
                scrolls=object(),
            ),
            start_time=datetime.now(),
            limit_time=timedelta(minutes=30),
            user_status='alone',
            activate_realm_raid=lambda *_: None,
        )
        return task

    def test_boss_target_overrides_battle_limit(self):
        check_exit = load_method('base.py', 'BaseExploration', 'check_exit')
        task = self.make_task(boss_target=3, boss_count=2, battles=35)
        self.assertFalse(check_exit(task, None))
        task.boss_count = 3
        self.assertTrue(check_exit(task, None))

    def test_zero_boss_target_uses_battle_limit(self):
        check_exit = load_method('base.py', 'BaseExploration', 'check_exit')
        task = self.make_task(boss_target=0, boss_count=0, battles=30)
        self.assertTrue(check_exit(task, None))

    def test_time_limit_still_applies_with_boss_target(self):
        check_exit = load_method('base.py', 'BaseExploration', 'check_exit')
        task = self.make_task(boss_target=3, boss_count=1, battles=35)
        task.start_time = datetime.now() - timedelta(minutes=31)
        self.assertTrue(check_exit(task, None))

    def test_only_winning_boss_battle_counts(self):
        run_on_battle = load_method('script_task.py', 'ScriptTask', 'run_on_battle')
        task = self.make_task(boss_target=3, boss_count=0, battles=0)
        task.fire_monster_type = 'boss'
        task._match_end = SimpleNamespace(refresh=lambda: None)
        task._config.general_battle_config = object()
        task.run_general_battle = lambda *_args, **_kwargs: False
        run_on_battle(task)
        self.assertEqual(task.boss_count, 0)
        task.run_general_battle = lambda *_args, **_kwargs: True
        run_on_battle(task)
        self.assertEqual(task.boss_count, 1)
        task.fire_monster_type = 'normal'
        run_on_battle(task)
        self.assertEqual(task.boss_count, 1)


if __name__ == '__main__':
    unittest.main()
