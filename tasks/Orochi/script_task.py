# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
from time import sleep
from datetime import time, datetime, timedelta
import numpy as np
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig

from tasks.Component.GeneralBattle.general_battle import BattleAction, GeneralBattle, ExitMatcher, BattleContext
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralBuff.general_buff import GeneralBuff
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import any_of, page_main, page_reward, page_shikigami_records, page_soul_zones
from tasks.Orochi.assets import OrochiAssets
from tasks.Orochi.config import Orochi, UserStatus, Layer
from tasks.TrueOrochi.assets import TrueOrochiAssets
from module.base.timer import Timer
from module.base.utils import color_similar, get_color
from module.logger import logger
from module.exception import TaskEnd
from tasks.Orochi.page import page_orochi


# 新版御魂选层页「队伍预设」弹窗布局（1280x720）
_PRESET_GROUP_CLICK_X_RANGE = (428, 506)
_PRESET_GROUP_CLICK_Y_JITTER = 14
_PRESET_GROUP_SAMPLE_X = 420
_PRESET_GROUP_START_Y = 184
_PRESET_GROUP_STEP_Y = 51
_PRESET_GROUP_SELECTED_COLOR = (249.0, 215.0, 156.0)
_PRESET_GROUP_SELECTED_THRESHOLD = 28
_PRESET_GROUP_SCROLL_TOP_START_BOX = (435, 185, 500, 225)
_PRESET_GROUP_SCROLL_TOP_END_BOX = (435, 445, 500, 490)

_PRESET_TEAM_CLICK_X_RANGE = (575, 760)
_PRESET_TEAM_TITLE_Y_RANGE = (7, 25)
_PRESET_TEAM_TOP_Y = 158
_PRESET_TEAM_STEP_Y = 96
_PRESET_TEAM_VISIBLE_SLOTS = 3
_PRESET_TEAM_PURPLE_THRESHOLD = 80
_PRESET_TEAM_SCROLL_TOP_START_BOX = (600, 185, 840, 225)
_PRESET_TEAM_SCROLL_TOP_END_BOX = (600, 415, 840, 455)
_PRESET_TEAM_SWIPE_UP_START_BOX = (610, 405, 830, 435)
_PRESET_TEAM_SWIPE_UP_DY_RANGE = (92, 102)
_PRESET_TEAM_SWIPE_UP_DX_JITTER = 18
_PRESET_ENTRY_BRIGHTNESS_AREA = (752, 566, 800, 614)
_PRESET_ENTRY_NORMAL_BRIGHTNESS = 75.0
_PRESET_CLOSE_OUTSIDE_BOX = (260, 180, 355, 420)
_PRESET_STABLE_EXIT_CHECKS = 2


class ScriptTask(GeneralBattle, GeneralInvite, GeneralBuff, GeneralRoom, GameUi, SwitchSoul, OrochiAssets, TrueOrochiAssets):

    def _orochi_battle_key(self) -> str:
        return f"orochi_{self.config.orochi.orochi_config.layer}"

    def _register_custom_pages(self) -> None:
        reward_page = self.navigator.resolve_page(page_reward)
        if reward_page is None:
            return
        reward_page.recognizer = any_of(self.I_GI_SURE, self.I_GREED_GHOST, self.I_PET_PRESENT,
                                        reward_page.recognizer)

    def _exit_matcher(self) -> ExitMatcher | None:
        return any_of(self.I_GI_EMOJI_1, self.I_GI_EMOJI_2, self.I_CHECK_EXPLORATION)

    def _handle_reward(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        # 无论胜利与否, 都会出现是否邀请一次队友, 区别在于, 失败的话不会出现那个勾选默认邀请的框
        if self.config.orochi.orochi_config.user_status == UserStatus.LEADER and \
            self.check_and_invite(self.config.orochi.invite_config.default_invite):
            return BattleAction.CONTINUE
        return super()._handle_reward(context, config)

    def run(self) -> bool:
        self.switch_orochi_souls()

        limit_count = self.config.orochi.orochi_config.limit_count
        limit_time = self.config.orochi.orochi_config.limit_time
        self.current_count = 0
        self.limit_count: int = limit_count
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second)

        config: Orochi = self.config.orochi
        if not self.is_in_battle(True):
            self.goto_page(page_main)
            if config.orochi_config.soul_buff_enable:
                self.open_buff()
                self.soul(is_open=True)
                self.close_buff()

        success = True
        match config.orochi_config.user_status:
            case UserStatus.LEADER: success = self.run_leader()
            case UserStatus.MEMBER: success = self.run_member()
            case UserStatus.ALONE: self.run_alone()
            case UserStatus.WILD: success = self.run_wild()
            case _: logger.error('Unknown user status')

        # 御魂结束后检测是否出现真蛇
        if config.orochi_config.check_true_orochi_enable:
            self.goto_page(page_orochi)
            self.screenshot()
            if self.appear(self.I_FIND_TS):
                logger.info('Find true orochi after orochi battle, set TrueOrochi task to run now')
                self.set_next_run(task='TrueOrochi', success=False, finish=False, server=False, target=datetime.now())
        self.goto_page(page_main)
        # 记得关掉
        if config.orochi_config.soul_buff_enable:
            self.open_buff()
            self.soul(is_open=False)
            self.close_buff()
        # 下一次运行时间
        if success:
            self.set_next_run('Orochi', finish=True, success=True)
        else:
            self.set_next_run('Orochi', finish=False, success=False)

        raise TaskEnd

    def switch_orochi_souls(self):
        # 御魂切换方式一
        if self.config.orochi.switch_soul.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(self.config.orochi.switch_soul.switch_group_team)

        # 御魂切换方式二
        if self.config.orochi.switch_soul.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(self.config.orochi.switch_soul.group_name,
                                         self.config.orochi.switch_soul.team_name)
        # 根据选层切换御魂
        self.orochi_switch_soul()

    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        pos = self.list_find(self.L_LAYER_LIST, layer)
        if pos:
            self.device.click(x=pos[0], y=pos[1], control_name=f'LAYER_{layer}')
            return True
        return False

    @staticmethod
    def _random_point_in_box(box: tuple[int, int, int, int]) -> tuple[int, int]:
        x1, y1, x2, y2 = box
        return random.randint(x1, x2), random.randint(y1, y2)

    @staticmethod
    def _count_preset_slot_purple_pixels(image, slot_index: int) -> int:
        """统计指定队伍卡片左右边框的紫色高亮像素数，避开上下相邻卡片交界。"""
        y_top = _PRESET_TEAM_TOP_Y + slot_index * _PRESET_TEAM_STEP_Y
        y1, y2 = y_top + 15, y_top + 75
        total = 0
        for x1, x2 in ((534, 546), (916, 928)):
            patch = image[y1:y2, x1:x2]
            r = patch[:, :, 0].astype(int)
            g = patch[:, :, 1].astype(int)
            b = patch[:, :, 2].astype(int)
            total += int(((b > 165) & (r > 100) & ((b - g) > 65)).sum())
        return total

    def _is_preset_overlay_clear(self) -> bool:
        """判断队伍预设及御魂确认弹窗是否已关闭且选层页恢复正常亮度。"""
        if self.appear(self.I_PRESET_DEPLOY) or self.appear(self.I_PRESET_CONFIRM):
            return False
        x1, y1, x2, y2 = _PRESET_ENTRY_BRIGHTNESS_AREA
        return float(np.mean(self.device.image[y1:y2, x1:x2])) >= _PRESET_ENTRY_NORMAL_BRIGHTNESS

    def _dismiss_preset_popup_if_open(self) -> None:
        """超时回退前清理残留的队伍预设弹窗，避免后续隔着弹窗误点挑战。"""
        close_timer = Timer(3).start()
        while not close_timer.reached():
            self.screenshot()
            if self._is_preset_overlay_clear():
                return
            if self.appear_then_click(self.I_PRESET_CONFIRM, interval=1):
                sleep(0.35)
                continue
            cx, cy = self._random_point_in_box(_PRESET_CLOSE_OUTSIDE_BOX)
            self.device.click(x=cx, y=cy, control_name='OROCHI_PRESET_DISMISS')
            sleep(0.35)

    def switch_orochi_preset_before_battle(self) -> bool:
        """在八岐大蛇选层页通过新版「队伍预设」弹窗直接切换出战队伍。

        支持在开启「锁定阵容」及队长/单人/野队模式下战前换队；若当前客户端界面
        未识别到新版「队伍预设」入口，则返回 False 自动回退原有战中准备页切队逻辑。
        """
        battle_cfg = self.config.orochi.general_battle_config
        if not battle_cfg.preset_enable:
            logger.info('八岐大蛇未开启通用战斗预设队伍（preset_enable=False），跳过战前切队')
            return False

        preset_group = max(1, min(7, int(battle_cfg.preset_group or 1)))
        preset_team = max(1, int(battle_cfg.preset_team or 1))
        logger.info(f'八岐大蛇准备战前切换预设队伍：预设组 {preset_group}，队伍 {preset_team}')
        # 选层后稍作缓冲，等待选层页稳定后再点击队伍预设
        sleep(0.5)

        # 1. 检测新版选层页「队伍预设」入口并打开弹窗
        open_timer = Timer(4).start()
        opened = False
        seen_entry = False
        while True:
            if open_timer.reached():
                break
            self.screenshot()
            if self.appear(self.I_PRESET_DEPLOY):
                opened = True
                break
            if self.appear_then_click(self.I_TEAM_PRESET, interval=1):
                seen_entry = True
                sleep(0.4)
                continue
            if not seen_entry and open_timer.current() >= 1.5:
                logger.info('选层页未识别到新版队伍预设入口，回退至战斗准备页切队逻辑')
                return False

        if not opened:
            logger.warning('打开八岐大蛇队伍预设弹窗超时，回退至战斗准备页切队逻辑')
            return False

        # 2. 先将左侧分组列表向下滑回最顶部，确保第 1 格为「常用」、第 2 格为「挖土」等原始顺序
        for _ in range(2):
            self.device.swipe(
                p1=self._random_point_in_box(_PRESET_GROUP_SCROLL_TOP_START_BOX),
                p2=self._random_point_in_box(_PRESET_GROUP_SCROLL_TOP_END_BOX),
            )
            sleep(0.4)

        # 3. 正向校验并选中左侧预设分组（1~7）：确认采样区变为暖金色选中态
        group_y = _PRESET_GROUP_START_Y + (preset_group - 1) * _PRESET_GROUP_STEP_Y
        group_sample_area = (_PRESET_GROUP_SAMPLE_X, group_y - 4, _PRESET_GROUP_SAMPLE_X + 10, group_y + 5)
        group_click_box = (
            _PRESET_GROUP_CLICK_X_RANGE[0],
            group_y - _PRESET_GROUP_CLICK_Y_JITTER,
            _PRESET_GROUP_CLICK_X_RANGE[1],
            group_y + _PRESET_GROUP_CLICK_Y_JITTER,
        )
        group_timer = Timer(4).start()
        group_selected = False
        last_group_color = None
        while True:
            if group_timer.reached():
                logger.warning(f'选择预设分组 {preset_group} 超时（最后采样 RGB={last_group_color}），继续尝试选择队伍')
                break
            self.screenshot()
            last_group_color = get_color(self.device.image, group_sample_area)
            if color_similar(last_group_color, _PRESET_GROUP_SELECTED_COLOR, threshold=_PRESET_GROUP_SELECTED_THRESHOLD):
                group_selected = True
                logger.info(f'已确认选中预设分组 {preset_group}（RGB={[round(c, 1) for c in last_group_color]}）')
                break
            gx, gy = self._random_point_in_box(group_click_box)
            self.device.click(x=gx, y=gy, control_name=f'OROCHI_PRESET_GROUP_{preset_group}')
            sleep(0.45)

        if group_selected:
            sleep(0.35)

        # 4. 将右侧队伍列表先拉回最顶部，避免上次停留在同一分组且已下滑导致槽位错位
        self.device.swipe(
            p1=self._random_point_in_box(_PRESET_TEAM_SCROLL_TOP_START_BOX),
            p2=self._random_point_in_box(_PRESET_TEAM_SCROLL_TOP_END_BOX),
        )
        sleep(0.4)

        # 5. 定位并选中右侧预设队伍（1~3 直接点标题栏，超过 3 队向上滑动后点第 3 槽位）
        if preset_team <= _PRESET_TEAM_VISIBLE_SLOTS:
            slot_index = preset_team - 1
        else:
            swipe_steps = preset_team - _PRESET_TEAM_VISIBLE_SLOTS
            logger.info(f'目标队伍 {preset_team} 超过前 {_PRESET_TEAM_VISIBLE_SLOTS} 队，右侧列表上滑 {swipe_steps} 步')
            for _ in range(swipe_steps):
                sx, sy = self._random_point_in_box(_PRESET_TEAM_SWIPE_UP_START_BOX)
                ex = max(
                    _PRESET_TEAM_SWIPE_UP_START_BOX[0],
                    min(_PRESET_TEAM_SWIPE_UP_START_BOX[2], sx + random.randint(-_PRESET_TEAM_SWIPE_UP_DX_JITTER, _PRESET_TEAM_SWIPE_UP_DX_JITTER)),
                )
                ey = sy - random.randint(_PRESET_TEAM_SWIPE_UP_DY_RANGE[0], _PRESET_TEAM_SWIPE_UP_DY_RANGE[1])
                self.device.swipe(p1=(sx, sy), p2=(ex, ey))
                sleep(0.4)
            slot_index = _PRESET_TEAM_VISIBLE_SLOTS - 1

        team_y_top = _PRESET_TEAM_TOP_Y + slot_index * _PRESET_TEAM_STEP_Y
        team_click_box = (
            _PRESET_TEAM_CLICK_X_RANGE[0],
            team_y_top + _PRESET_TEAM_TITLE_Y_RANGE[0],
            _PRESET_TEAM_CLICK_X_RANGE[1],
            team_y_top + _PRESET_TEAM_TITLE_Y_RANGE[1],
        )
        team_timer = Timer(4).start()
        team_selected = False
        last_purple_px = 0
        while True:
            if team_timer.reached():
                logger.warning(f'确认选中队伍 {preset_team}（槽位 {slot_index + 1}）超时，紫色边框像素={last_purple_px}')
                break
            self.screenshot()
            last_purple_px = self._count_preset_slot_purple_pixels(self.device.image, slot_index)
            if last_purple_px >= _PRESET_TEAM_PURPLE_THRESHOLD:
                team_selected = True
                logger.info(f'已确认选中队伍 {preset_team}（槽位 {slot_index + 1}，紫色边框像素={last_purple_px}）')
                break
            tx, ty = self._random_point_in_box(team_click_box)
            self.device.click(x=tx, y=ty, control_name=f'OROCHI_PRESET_TEAM_{preset_team}')
            sleep(0.45)

        if not team_selected:
            logger.warning(f'未能确认目标队伍 {preset_team} 处于选中状态，仍尝试点击出战')
        else:
            sleep(0.3)

        # 6. 点击「出战」；若弹出“御魂不一致，是否自动装配御魂并出战”确认框则点击「确定」，
        #    并连续 2 次稳定截图确认两个弹窗都消失且选层页恢复正常亮度（防卡顿延迟弹窗抢跑）
        deploy_timer = Timer(7).start()
        deployed = False
        clicked_deploy = False
        stable_clear_count = 0
        while True:
            if deploy_timer.reached():
                break
            self.screenshot()
            if self.appear_then_click(self.I_PRESET_CONFIRM, interval=1):
                logger.info('检测到御魂不一致确认弹窗，已点击「确定」自动装配御魂并出战')
                clicked_deploy = True
                stable_clear_count = 0
                sleep(0.4)
                continue
            if self.appear_then_click(self.I_PRESET_DEPLOY, interval=1):
                clicked_deploy = True
                stable_clear_count = 0
                sleep(0.5)
                continue
            if clicked_deploy and self._is_preset_overlay_clear():
                stable_clear_count += 1
                if stable_clear_count >= _PRESET_STABLE_EXIT_CHECKS:
                    deployed = True
                    break
                sleep(0.3)
            else:
                stable_clear_count = 0
                sleep(0.2)

        if not deployed:
            logger.warning('点击队伍预设「出战」后弹窗未完全关闭，尝试关闭残留弹窗并回退至战斗准备页切队逻辑')
            self._dismiss_preset_popup_if_open()
            return False

        self.mark_battle_behavior_done(self._orochi_battle_key(), "preset")
        logger.info(f'八岐大蛇战前切换预设队伍成功：分组 {preset_group}，队伍 {preset_team}')
        return True

    def run_leader(self):
        logger.info('Start run leader')
        self.goto_page(page_orochi)
        layer = self.config.orochi.orochi_config.layer
        self.check_layer(layer)
        self.switch_orochi_preset_before_battle()
        # https://github.com/runhey/OnmyojiAutoScript/issues/592
        self.config.orochi.general_battle_config.lock_team_enable = True
        self.check_lock(self.config.orochi.general_battle_config.lock_team_enable, self.I_OROCHI_LOCK, self.I_OROCHI_UNLOCK)
        # 创建队伍
        logger.info('Create team')
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_TEAM):
                break
            if self.appear_then_click(self.I_FORM_TEAM, interval=1):
                continue
        # 创建房间
        self.create_room()
        self.ensure_private()
        self.create_ensure()
        # 邀请队友
        success = True
        is_first = True
        # 这个时候我已经进入房间了哦
        while 1:
            self.screenshot()
            if self.current_count >= self.limit_count:
                if self.is_in_room():
                    logger.info(f'八岐大蛇已完成 {self.current_count}/{self.limit_count} 次，达到次数上限')
                    break
            if datetime.now() - self.start_time >= self.limit_time:
                if self.is_in_room():
                    logger.info('八岐大蛇已达到运行时长上限')
                    break
            # 如果没有进入房间那就不需要后面的邀请
            if not self.is_in_room():
                if self.is_room_dead():
                    logger.warning('八岐大蛇任务失败')
                    success = False
                    break
                continue
            # 点击挑战
            if not is_first:
                if self.run_invite(config=self.config.orochi.invite_config):
                    self.run_general_battle(
                        config=self.config.orochi.general_battle_config,
                        battle_key=self._orochi_battle_key()
                    )
                else:
                    # 邀请失败，退出任务
                    logger.warning('邀请队友失败，结束八岐大蛇任务')
                    success = False
                    break
            # 第一次会邀请队友
            if is_first:
                if not self.run_invite(config=self.config.orochi.invite_config, is_first=True):
                    logger.warning('邀请队友失败，结束八岐大蛇任务')
                    success = False
                    break
                else:
                    is_first = False
                    self.run_general_battle(
                        config=self.config.orochi.general_battle_config,
                        battle_key=self._orochi_battle_key()
                    )

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass
        if not success:
            return False
        return True

    def run_member(self):
        logger.info('Start run member')
        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=1):
                continue
            if self.current_count >= self.limit_count:
                logger.info(f'八岐大蛇已完成 {self.current_count}/{self.limit_count} 次，达到次数上限')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('八岐大蛇已达到运行时长上限')
                break

            if self.check_then_accept():
                continue

            if self.is_in_room(False):
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=self.config.orochi.invite_config.wait_time):
                    self.run_general_battle(
                        config=self.config.orochi.general_battle_config,
                        battle_key=self._orochi_battle_key()
                    )
                else:
                    break
            # 队长秒开的时候，检测是否进入到战斗中
            if self.is_in_battle(False):
                self.run_general_battle(
                    config=self.config.orochi.general_battle_config,
                    battle_key=self._orochi_battle_key()
                )

        while 1:
            # 有一种情况是本来要退出的，但是队长邀请了进入的战斗的加载界面
            if self.appear(self.I_CHECK_MAIN) or self.appear(self.I_CHECK_EXPLORATION):
                break
            # 如果可能在房间就退出
            if self.exit_room():
                pass
            # 如果还在战斗中，就退出战斗
            if self.exit_battle():
                pass

        return True

    def run_alone(self):
        logger.info('Start run alone')
        self.goto_page(page_orochi)
        layer = self.config.orochi.orochi_config.layer
        self.check_layer(layer)
        self.switch_orochi_preset_before_battle()
        self.check_lock(self.config.orochi.general_battle_config.lock_team_enable, self.I_OROCHI_LOCK, self.I_OROCHI_UNLOCK)

        def is_in_orochi(screenshot=False) -> bool:
            if screenshot:
                self.screenshot()
            return self.appear(self.I_OROCHI_FIRE)

        while 1:
            self.screenshot()
            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=1):
                continue
            if not is_in_orochi():
                continue
            if self.current_count >= self.limit_count:
                logger.info(f'八岐大蛇已完成 {self.current_count}/{self.limit_count} 次，达到次数上限')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('八岐大蛇已达到运行时长上限')
                break
            # 点击挑战
            while True:
                self.screenshot()
                if self.appear_then_click(self.I_OROCHI_FIRE, interval=1):
                    pass
                if not self.appear(self.I_OROCHI_FIRE):
                    self.run_general_battle(
                        config=self.config.orochi.general_battle_config,
                        battle_key=self._orochi_battle_key(),
                        exit_matcher=self.I_OROCHI_FIRE)
                    break

    def run_wild(self):
        logger.info('Start run wild')

        # 已经在战斗中不必初始化，保证已经组队开始战斗的情况下可以自动执行后续任务
        if not self.is_in_battle(True):
            self.goto_page(page_orochi)
            layer = self.config.orochi.orochi_config.layer
            self.check_layer(layer)
            self.switch_orochi_preset_before_battle()
            self.check_lock(self.config.orochi.general_battle_config.lock_team_enable, self.I_OROCHI_LOCK, self.I_OROCHI_UNLOCK)
            # 创建队伍
            logger.info('Create team')
            while 1:
                self.screenshot()
                if self.appear(self.I_CHECK_TEAM):
                    break
                if self.appear_then_click(self.I_FORM_TEAM, interval=1):
                    continue
            # 创建房间
            self.create_room()
            self.ensure_public()
            self.create_ensure()

        success = True
        while 1:
            self.screenshot()
            # 无论胜利与否, 都会出现是否邀请一次队友
            # 区别在于，失败的话不会出现那个勾选默认邀请的框
            if self.check_and_invite(self.config.orochi.invite_config.default_invite):
                continue

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_RANDOM_RIGHT, interval=1):
                continue

            if self.current_count >= self.limit_count:
                if self.is_in_room():
                    logger.info(f'八岐大蛇已完成 {self.current_count}/{self.limit_count} 次，达到次数上限')
                    break

            if datetime.now() - self.start_time >= self.limit_time:
                if self.is_in_room():
                    logger.info('八岐大蛇已达到运行时长上限')
                    break

            if not self.is_in_room():
                if self.is_room_dead():
                    logger.warning('八岐大蛇任务失败')
                    success = False
                    break
                continue

            # 点击挑战
            logger.info('Wait for starting')
            while 1:
                self.screenshot()
                # 在进入战斗前必然会出现挑战界面，因此点击失败必须重复点击，防止卡在挑战界面，
                # 点击成功后如果网络卡顿，导致没有进入战斗，则无法进入 run_general_battle 流程，
                # 所以如果判断是在战斗中，则执行通用战斗流程
                if not self.is_in_battle(False):
                    if not self.is_in_room() and self.is_room_dead():
                        break
                    if not self.appear_then_click(self.I_OROCHI_WILD_FIRE, interval=1, threshold=0.8):
                        continue

                self.screenshot()
                if not self.appear(self.I_OROCHI_WILD_FIRE, threshold=0.8):
                    self.run_general_battle(
                        config=self.config.orochi.general_battle_config,
                        battle_key=self._orochi_battle_key(),
                        exit_matcher=any_of(self.I_OROCHI_WILD_FIRE, self.I_CHECK_TEAM),
                    )
                    break

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass

        if not success:
            return False
        return True

    def is_room_dead(self) -> bool:
        # 如果在探索界面或者是出现在组队界面，那就是可能房间死了
        sleep(0.5)
        if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
            sleep(0.5)
            if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                return True
        return False

    def orochi_switch_soul(self) -> None:
        # 判断是否开启根据选层切换御魂
        orochi_switch_soul = self.config.orochi.switch_soul
        if not orochi_switch_soul.auto_switch_soul:
            return
        group_team: str = ''
        layer = self.config.orochi.orochi_config.layer
        match layer:
            case Layer.TEN:
                group_team = orochi_switch_soul.ten_switch
            case Layer.ELEVEN:
                group_team = orochi_switch_soul.eleven_switch
            case Layer.TWELVE:
                group_team = orochi_switch_soul.twelve_switch
            case Layer.THIRTEEN:
                group_team = orochi_switch_soul.thirteen_switch
        self.goto_page(page_shikigami_records)
        self.run_switch_soul(group_team)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('日常2')
    d = Device(c)
    t = ScriptTask(c, d)

    t._open_invite_panel_if_needed(True)
