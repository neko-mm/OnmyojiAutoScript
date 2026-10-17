import logging
import unittest

from module.log_localization import LocalizedLogFilter, localize_log_text, page_log_label


class LogLocalizationTest(unittest.TestCase):
    def test_exact_message_and_heading(self):
        self.assertEqual(localize_log_text("Open buff"), "打开加成界面")
        self.assertEqual(localize_log_text("APP LOGIN"), "游戏登录")
        self.assertEqual(localize_log_text("DAILYTRIFLES"), "每日琐事")
        self.assertEqual(localize_log_text("游戏登录"), "游戏登录")
        self.assertEqual(page_log_label("page_battle"), "战斗中（page_battle）")
        self.assertEqual(page_log_label("page_future"), "page_future")

    def test_dynamic_values_are_preserved(self):
        self.assertEqual(
            localize_log_text('Exact match friend "小明" in I_FRIEND at (10, 20)'),
            '找到好友“小明”，匹配规则 I_FRIEND，位置 (10, 20)',
        )
        self.assertEqual(
            localize_log_text('ADB connect 127.0.0.1:7555 failed: timeout'),
            'ADB 连接 127.0.0.1:7555 失败：timeout',
        )
        self.assertEqual(
            localize_log_text('UI goto page_main'),
            '前往页面：庭院（page_main）',
        )

    def test_unknown_and_machine_readable_records_are_unchanged(self):
        for message in (
            '[0.18s] Click (1224, 276) @ SAFE_RANDOM_CLICK',
            '[Task] ActivityShikigami (Enable, 1, 2026-10-17 12:00:00)',
            '[UI] 战斗中（page_battle）',
            'D:\\App\\OAS\\deploy.yaml',
            'Unknown future log',
            'GameStuckError: Wait too long',
        ):
            self.assertEqual(localize_log_text(message), message)

    def test_navigation_explains_pages_and_preserves_failure_weight(self):
        result = localize_log_text(
            'Transition failed before leaving page_main: page_main->page_act, penalty=1.0'
        )
        self.assertEqual(
            result,
            '从 庭院（page_main） 跳转失败：庭院（page_main）->活动主页（page_act），路径失败权重 1.0',
        )
        self.assertEqual(localize_log_text(result), result)
        self.assertIn('各跳转路径的失败权重', localize_log_text('Edge penalties: {}'))
        self.assertEqual(
            localize_log_text('Current page: 庭院（page_main）'),
            '当前页面：庭院（page_main）',
        )

    def test_game_context_keeps_retries_separate_from_tickets(self):
        self.assertEqual(localize_log_text('Start run pass'), '开始门票挑战')
        self.assertEqual(localize_log_text('Check ap tickets'), '检查体力')
        self.assertEqual(
            localize_log_text('Try click fire, remain times[3]'),
            '尝试开始挑战，还可重试 3 次',
        )
        self.assertEqual(
            localize_log_text('Climb type pass count limit reached'),
            '门票挑战已达到设置的战斗场次',
        )

    def test_delegation_name_is_not_treated_as_an_image(self):
        self.assertEqual(
            localize_log_text('Delegation: 画 not found'),
            '当前委派列表中未找到“画”',
        )
        self.assertEqual(
            localize_log_text('Delegation: 猫老大 start'),
            '正在派遣委派“猫老大”',
        )

    def test_operations_do_not_claim_unconfirmed_results(self):
        self.assertEqual(
            localize_log_text('Switch main costume to costume_main_17'),
            '使用庭院皮肤识别方案：costume_main_17',
        )
        self.assertEqual(
            localize_log_text('Click team 4 failed in group 1'),
            '本次未能点击预设队伍（分组：1，队伍：4）',
        )
        self.assertEqual(
            localize_log_text('Switch soul_one group 1 team 4'),
            '预设切换操作结束（分组：1，队伍：4）',
        )

    def test_filter_keeps_metadata_and_formats_arguments(self):
        record = logging.LogRecord(
            'oas', logging.INFO, 'example.py', 42,
            'Need invite friend list: %s', (['小明'],), None,
        )
        self.assertTrue(LocalizedLogFilter().filter(record))
        self.assertEqual(record.getMessage(), "待邀请好友：['小明']")
        self.assertEqual((record.levelno, record.pathname, record.lineno),
                         (logging.INFO, 'example.py', 42))


if __name__ == '__main__':
    unittest.main()
