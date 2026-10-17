import importlib.util
import sys
import unittest
from pathlib import Path
from module.log_localization import localize_log_text


source = Path(__file__).resolve().parents[1] / 'module/server/log_stats.py'
spec = importlib.util.spec_from_file_location('oas_log_stats_test', source)
log_stats = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = log_stats
spec.loader.exec_module(log_stats)


class LogStatsBattleHeadingTest(unittest.TestCase):
    def test_localized_task_heading_keeps_battle_statistics(self):
        task = localize_log_text('ActivityShikigami')
        lines = [
            '═' * 80,
            '─' * 35 + f' {task} ' + '─' * 35,
            '═' * 80,
            '2026-10-17 12:00:00.000 | logger.py | INFO | 开始门票挑战',
            '─' * 35 + ' 开始战斗 ' + '─' * 35,
            '2026-10-17 12:00:01.000 | logger.py | INFO | 开始战斗',
            '2026-10-17 12:00:11.000 | logger.py | INFO | 战斗结果：胜利',
        ]
        result = log_stats.LogStatsParser.parse_lines(lines)
        self.assertEqual(result['total_battle_count'], 1)
        self.assertEqual(result['tasks'][task]['battle']['avg_duration_seconds'], 10)

    def test_chinese_and_english_battle_headings(self):
        for heading in ('开始战斗', 'GENERAL BATTLE START'):
            with self.subTest(heading=heading):
                lines = [
                    '═' * 80,
                    '─' * 35 + ' 探索 ' + '─' * 35,
                    '═' * 80,
                    '2026-10-12 12:00:00.000 | logger.py | INFO | 探索',
                    '─' * 35 + f' {heading} ' + '─' * 35,
                    '2026-10-12 12:00:01.000 | logger.py | INFO | 开始战斗',
                    '2026-10-12 12:00:11.000 | logger.py | INFO | 战斗结果：胜利',
                ]
                result = log_stats.LogStatsParser.parse_lines(lines)
                self.assertEqual(result['total_battle_count'], 1)
                self.assertEqual(result['tasks']['探索']['battle']['avg_duration_seconds'], 10)


if __name__ == '__main__':
    unittest.main()
