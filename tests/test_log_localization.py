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
            '[UI] 战斗中（page_battle）',
            'D:\\App\\OAS\\deploy.yaml',
            'Unknown future log',
        ):
            self.assertEqual(localize_log_text(message), message)

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
