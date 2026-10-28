# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import GameTooManyClickError, TaskEnd
from module.base.timer import Timer
from module.atom.click import RuleClick

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_delegation
from tasks.Delegation.config import DelegationConfig
from tasks.Delegation.assets import DelegationAssets


class ScriptTask(GameUi, DelegationAssets):

    def run(self):
        self.navigator.add_unknown_closer(self._recover_reward_screen)
        self.goto_page(page_delegation)
        self.check_reward()
        con: DelegationConfig = self.config.delegation.delegation_config
        if con.miyoshino_painting:
            self.delegate_one('画')
        if con.bird_feather:
            self.delegate_one('鸟羽')
        if con.find_earring:
            self.delegate_one('寻找耳环')
        if con.cat_boss:
            self.delegate_one('猫老大')
        if con.miyoshino:
            self.delegate_one('接送')
        if con.strange_trace:
            self.delegate_one('痕迹')


        self.set_next_run(task='Delegation', success=True, finish=True)
        raise TaskEnd

    def delegate_one(self, name: str) -> bool:
        """
        委派一个任务
        :param name:
        :return:
        """
        def ui_click(click, stop):
            while 1:
                self.screenshot()
                if self.appear(stop):
                    break
                if self.click(click, interval=1.5):
                    continue
        logger.hr('Delegation one', 2)
        self.O_D_NAME.keyword = name
        self.screenshot()
        if not self.ocr_appear(self.O_D_NAME):
            logger.warning(f'Delegation: {name} not found')
            return False
        while 1:
            self.screenshot()
            if self.appear(self.I_D_START):
                break
            # 如果出现’召回‘ ’返回‘ 说明这个是现在委派中
            # 需要退出
            if self.appear(self.I_D_BACK):
                logger.warning(f'Delegation: {name} is in delegation')
                self.ui_click_until_disappear(self.I_D_BACK)
                self.wait_until_appear(self.I_REWARDS_MIN)
                return False
            if self.appear_then_click(self.I_D_SKIP, interval=0.8):
                continue
            if self.appear_then_click(self.I_D_CONFIRM, interval=0.8):
                continue
            if self.appear(self.I_D_CONFIRM):
                continue
            if self._recover_reward_screen():
                self.check_reward()
                self.screenshot()
                if self.appear(self.I_D_CONFIRM) or self.appear(self.I_D_START):
                    continue
                if not self.ocr_appear(self.O_D_NAME):
                    logger.info(f'委派“{name}”的领奖流程已结束，当前列表中已无该委派')
                    return False
                continue
            if self.ocr_appear_click(self.O_D_NAME, interval=1):
                continue
        # 进入委派  fefe e  fe
        logger.info(f'Enter Delegation: {name}')
        ui_click(self.C_D_1, self.I_D_SELECT_1)
        ui_click(self.C_D_2, self.I_D_SELECT_2)
        ui_click(self.C_D_3, self.I_D_SELECT_3)
        ui_click(self.C_D_4, self.I_D_SELECT_4)
        # 委派开始
        logger.info(f'Delegation: {name} start')
        while 1:
            self.screenshot()
            if not self.appear(self.I_D_START):
                break
            if self.click(self.C_D_5, interval=0.8):
                continue
            if self.appear_then_click(self.I_D_START, interval=1.8):
                continue
        # ui_click(self.C_D_5, self.I_D_SELECT_5)
        # self.ui_click_until_disappear(self.I_D_START)

    def _advance_reward_dialogue(self):
        for marker, speaker in ((self.I_REWARDS_IBUKI_DIALOGUE, '伊吹'),
                                (self.I_REWARDS_HIROMASA_DIALOGUE, '源博雅')):
            if self.appear_then_click(marker, action=self.C_REWARDS_DIALOGUE_CONTINUE, interval=1):
                logger.info(f'继续式神委派的{speaker}对话')
                return marker
        return None

    def _handle_reward_screen(self):
        if self.appear(self.I_D_CONFIRM) or self.appear(self.I_D_START):
            return None
        # 名字牌会留在领奖弹窗后面，先处理按钮，不能只凭名字继续对话。
        for button in (self.I_REWARDS_DONE, self.I_REWARDS_GET, self.I_REWARDS_FALSE,
                       self.I_CHAT_1, self.I_CHAT_2):
            if self.appear(button):
                if self.appear_then_click(button, interval=1):
                    return button
                return None
        return self._advance_reward_dialogue() or None

    def _recover_reward_screen(self):
        return self._handle_reward_screen() is not None

    def _click_completed_reward(self):
        rule = self.O_D_DONE
        results = rule.detect_and_ocr(self.device.image)
        completed = [result for result in results if result.ocr_text.strip() == '完成']
        if not completed:
            return False
        # 每次只选一个地图标记，避免多个文字框合并后点到空白处。
        result = min(completed, key=lambda item: (item.box[0][1], item.box[0][0]))
        left = min(point[0] for point in result.box) + rule.roi[0]
        right = max(point[0] for point in result.box) + rule.roi[0]
        top = min(point[1] for point in result.box) + rule.roi[1]
        width = min(64, max(32, right - left))
        area = (int((left + right - width) / 2), int(top - 52), int(width), 40)
        x, y, w, h = area
        rx, ry, rw, rh = rule.roi
        if x < rx or y < ry or x + w > rx + rw or y + h > ry + rh:
            return False
        target = RuleClick(roi_front=area, roi_back=area, name=rule.name)
        return self.click(target, interval=1.5)

    def check_reward(self):
        check_timer = Timer(3)
        check_timer.start()
        last_button = None
        click_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_D_CONFIRM) or self.appear(self.I_D_START):
                return
            clicked = self._handle_reward_screen()
            if clicked is not None:
                if last_button is not None and last_button != clicked:
                    self.device.click_record_remove(last_button)
                last_button = clicked
                click_count += 1
                if click_count >= 40:
                    raise GameTooManyClickError('Delegation reward: too many clicks')
                check_timer.reset()
                continue
            if not self.appear(self.I_REWARDS_MIN):
                if self.appear_then_click(self.I_REWARDS_PANEL_COLLAPSED, interval=1):
                    check_timer.reset()
                continue
            if check_timer.reached():
                break
            if self._click_completed_reward():
                if last_button is not None and last_button != self.O_D_DONE:
                    self.device.click_record_remove(last_button)
                last_button = self.O_D_DONE
                click_count += 1
                if click_count >= 40:
                    raise GameTooManyClickError('Delegation reward: too many clicks')
                check_timer.reset()
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from memory_profiler import profile
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    # t.delegate_one('弥助的画')
    t.run()



