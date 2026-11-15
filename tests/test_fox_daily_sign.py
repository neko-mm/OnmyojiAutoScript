import unittest

from test_courtyard_soul_choice import CourtyardTask


class FoxDailySignTest(unittest.TestCase):
    def test_fox_courtyard_opens_sign_after_rewards(self):
        task = CourtyardTask(fox=True, sign=True)
        task.run_courtyard_affairs()
        self.assertIn(('click', 'draw_sign'), task.actions)
        self.assertIn(('click', 'close'), task.actions)
        self.assertLess(task.actions.index(('click', 'reward')),
                        task.actions.index(('click', 'fox_sign')))

    def test_other_courtyard_does_not_click_fox_sign(self):
        task = CourtyardTask(fox=False, sign=True)
        task.run_courtyard_affairs()
        self.assertNotIn(('click', 'fox_sign'), task.actions)

    def test_claimed_fox_sign_is_skipped(self):
        task = CourtyardTask(fox=True, sign=False)
        task.run_courtyard_affairs()
        self.assertNotIn(('click', 'close'), task.actions)


if __name__ == '__main__':
    unittest.main()
