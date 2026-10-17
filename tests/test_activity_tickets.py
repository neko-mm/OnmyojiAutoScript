import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


def load_check_tickets():
    source = Path(__file__).resolve().parents[1] / 'tasks/ActivityShikigami/base_act.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'BaseAct')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'check_tickets_enough')
    scope = {'logger': SimpleNamespace(hr=lambda *_: None, info=lambda *_: None)}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
    return scope['check_tickets_enough']


class TicketTask:
    climb_type = 'pass'

    def __init__(self, previous, readings, cost=1):
        self.pre_tickets_map = {'pass': previous}
        self.readings = iter(readings)
        self.device = SimpleNamespace(image=None)
        self.O_REMAIN_PASS = SimpleNamespace(ocr_digit=lambda _: next(self.readings))
        self.required_pass_tickets = lambda: cost

    def screenshot(self):
        pass


class ActivityTicketsTest(unittest.TestCase):
    def test_button_cost_recognition_retries_and_rejects_unknown_values(self):
        source = Path(__file__).resolve().parents[1] / 'tasks/ActivityShikigami/activities/normal.py'
        tree = ast.parse(source.read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'required_pass_tickets')
        scope = {'GameStuckError': ValueError}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
        for readings, expected in (([1], 1), ([5], 5), ([0, 5], 5)):
            values = iter(readings)
            task = SimpleNamespace(device=SimpleNamespace(image=None), screenshot=lambda: None,
                                   O_PASS_COST=SimpleNamespace(ocr_digit=lambda _: next(values)))
            self.assertEqual(scope['required_pass_tickets'](task), expected)
        values = iter([0, 0])
        with self.assertRaisesRegex(ValueError, '无法识别挑战按钮上的门票消耗'):
            scope['required_pass_tickets'](task)

    def test_five_ticket_battles_stop_at_zero(self):
        task = TicketTask(20, [15, 15, 10, 10, 5, 5, 0, 0])
        check = load_check_tickets()
        self.assertEqual([check(task) for _ in range(4)], [True, True, True, False])
        self.assertEqual(task.pre_tickets_map['pass'], 0)

    def test_empty_ocr_is_rechecked_before_stopping(self):
        task = TicketTask(5, [0, 5])
        self.assertTrue(load_check_tickets()(task))
        self.assertEqual(task.pre_tickets_map['pass'], 5)

    def test_confirmed_zero_stops_even_after_large_drop(self):
        self.assertFalse(load_check_tickets()(TicketTask(10, [0, 0])))

    def test_normal_reading_does_not_need_confirmation(self):
        self.assertTrue(load_check_tickets()(TicketTask(5, [4])))

    def test_less_than_five_tickets_stops_five_ticket_mode(self):
        for remaining in range(1, 5):
            with self.subTest(remaining=remaining):
                task = TicketTask(remaining + 5, [remaining, remaining], cost=5)
                self.assertFalse(load_check_tickets()(task))

    def test_exactly_five_tickets_can_start(self):
        self.assertTrue(load_check_tickets()(TicketTask(10, [5, 5], cost=5)))

    def test_single_ticket_mode_can_use_last_ticket(self):
        self.assertTrue(load_check_tickets()(TicketTask(2, [1], cost=1)))

    def test_zero_at_start_stops(self):
        self.assertFalse(load_check_tickets()(TicketTask(-1, [0, 0])))

    def test_other_resource_types_still_read_their_own_rules(self):
        check = load_check_tickets()
        for mode in ('ap', 'ap100', 'boss'):
            with self.subTest(mode=mode):
                task = TicketTask(-1, [])
                task.climb_type = mode
                task.pre_tickets_map = {mode: -1}
                rule = SimpleNamespace(ocr_digit=lambda _: 3,
                                       ocr_digit_counter=lambda _: (7, 3, 10))
                setattr(task, f'O_REMAIN_{mode.upper()}', rule)
                self.assertTrue(check(task))
                self.assertEqual(task.pre_tickets_map[mode], 3)

    def test_map_return_uses_map_specific_button(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'tasks/ActivityShikigami/page.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and any(keyword.arg == 'key' and isinstance(keyword.value, ast.Constant)
                         and keyword.value.value == 'page_act_map->page_act'
                         for keyword in node.keywords)]
        self.assertEqual(len(calls), 1)
        self.assertEqual(ast.unparse(calls[0].args[1]), 'ActivityShikigamiAssets.I_MAP_BACK')
        rules = json.loads((root / 'tasks/ActivityShikigami/as/pages.json').read_text())
        rule = next(rule for rule in rules if rule['itemName'] == 'map_back')
        self.assertTrue((root / 'tasks/ActivityShikigami/as' / rule['imageName']).is_file())


if __name__ == '__main__':
    unittest.main()
