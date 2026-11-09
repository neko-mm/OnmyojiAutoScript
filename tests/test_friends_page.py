import ast
import __future__
import json
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = os.environ.get('OAS_FRIENDS_SCREENSHOT')


def friends_rule():
    return next(rule for rule in json.loads(
        (ROOT / 'tasks/GameUi/page/image_main.json').read_text())
        if rule['itemName'] == 'check_friends')


class FriendsPageTest(unittest.TestCase):
    def test_template_size_and_generated_rule_match_source(self):
        rule = friends_rule()
        raw = (ROOT / 'tasks/GameUi/page' / rule['imageName']).read_bytes()
        x, y, w, h = map(int, rule['roiFront'].split(','))
        rx, ry, rw, rh = map(int, rule['roiBack'].split(','))
        self.assertEqual(struct.unpack('!II', raw[16:24]), (w, h))
        self.assertTrue(0 <= rx <= x < x+w <= rx+rw <= 1280)
        self.assertTrue(0 <= ry <= y < y+h <= ry+rh <= 720)
        tree = ast.parse((ROOT / 'tasks/GameUi/assets.py').read_text())
        assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'I_CHECK_FRIENDS'
                                  for t in node.targets))
        actual = {kw.arg: ast.literal_eval(kw.value) for kw in assignment.value.keywords}
        self.assertEqual(actual, dict(
            roi_front=tuple(map(int, rule['roiFront'].split(','))),
            roi_back=tuple(map(int, rule['roiBack'].split(','))),
            threshold=rule['threshold'], method=rule['method'],
            file='./tasks/GameUi/page/' + rule['imageName']))

    @unittest.skipUnless(SCREENSHOT, '设置 OAS_FRIENDS_SCREENSHOT 后回放好友页截图')
    def test_recent_tab_is_recognized_without_contacts_or_chat_content(self):
        import cv2
        import numpy as np

        # 只加载真实匹配方法，避免启动图像服务和连接游戏设备。
        tree = ast.parse((ROOT / 'module/image/runtime.py').read_text())
        runtime = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ImageRuntime')
        methods = [n for n in runtime.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('_crop', '_template_image_invalid', '_template_match_image')]
        cls = ast.ClassDef(name='Matcher', bases=[], keywords=[], body=methods, decorator_list=[])
        scope = {'cv2': cv2, 'np': np, 'logger': SimpleNamespace(debug=lambda *_: None)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                     '<image-runtime>', 'exec', flags=__future__.annotations.compiler_flag), scope)
        matcher = scope['Matcher']()
        rule = friends_rule()
        image = cv2.imread(SCREENSHOT)
        self.assertIsNotNone(image)
        template = cv2.imread(str(ROOT / 'tasks/GameUi/page' / rule['imageName']))
        roi = list(map(int, rule['roiBack'].split(',')))

        def matches(frame):
            return matcher._template_match_image(frame, template, roi, rule['threshold'], 'friends')[0]

        self.assertTrue(matches(image), '最近标签下的好友页面应识别成功')
        # 联系人、聊天区、左侧标签都不应影响页面识别。
        image[90:680, 138:1145] = 0
        self.assertTrue(matches(image))
        x, y, w, h = roi
        image[y:y+h, x:x+w] = 0
        self.assertFalse(matches(image), '缺少页面标志时不能误判好友页')


if __name__ == '__main__':
    unittest.main()
