import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


def load_exploration_loop():
    source = Path(__file__).resolve().parents[1] / 'tasks/Exploration/script_task.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ScriptTask')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'exec_exp_page')
    scope = {
        'pages': SimpleNamespace(page_battle_team_exit=SimpleNamespace(connect=lambda *_args, **_kwargs: None),
                                 page_exp_entrance='entrance'),
    }
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
    return scope['exec_exp_page']


class ExplorationRewardPopupTest(unittest.TestCase):
    def test_reward_popup_is_closed_before_detecting_map_or_stopping(self):
        actions = []
        reward_visible = [True]

        def close_reward():
            if not reward_visible[0]:
                return False
            actions.append('close_reward')
            reward_visible[0] = False
            return True

        def get_page():
            actions.append('detect_map')
            return 'map'

        task = SimpleNamespace(
            navigator=SimpleNamespace(resolve_page=lambda page: page),
            I_UI_CONFIRM='confirm',
            I_UI_CANCEL='cancel',
            screenshot=lambda: None,
            ui_reward_appear_click=close_reward,
            get_current_page=get_page,
            check_exit=lambda _page: True,
            appear_then_click=lambda *_args, **_kwargs: None,
        )
        load_exploration_loop()(task)
        self.assertEqual(actions, ['close_reward', 'detect_map'])


if __name__ == '__main__':
    unittest.main()
