from module.logger import logger
from module.base.timer import Timer
from module.exception import GameStuckError
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.base_act import BaseAct
import tasks.ActivityShikigami.page as pages
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher
from tasks.GameUi.page import all_of


class NormalClimbAct(BaseAct):
    """普通爬塔活动"""

    def required_pass_tickets(self) -> int:
        cost = self.O_PASS_COST.ocr_digit(self.device.image)
        if cost not in (1, 5):
            self.screenshot()
            cost = self.O_PASS_COST.ocr_digit(self.device.image)
        if cost not in (1, 5):
            raise GameStuckError("无法识别挑战按钮上的门票消耗，请检查当前挑战界面")
        return cost

    def _exit_matcher(self) -> ExitMatcher | None:
        return pages.any_of(self.I_ACT_FIRE, self.I_AS_BOSS_FIRE)

    def before_run(self):
        super().before_run()
        page_act = self.navigator.resolve_page(pages.page_act)
        page_act_pass = self.navigator.resolve_page(pages.page_act_pass)
        page_act_ap = self.navigator.resolve_page(pages.page_act_ap)
        page_act_map = self.navigator.resolve_page(pages.page_act_map)
        flag = pages.special_act_Flag

        if flag:
            # 体力爬塔和中转界面关联
            page_act_map.connect(
                page_act_ap,
                ActivityShikigamiAssets.I_MAP_GOTO_BATTLE,
                key="page_act_map->page_act_ap",
            )
        else:
            # 体力爬塔和主界面关联
            page_act.connect(
                page_act_ap,
                ActivityShikigamiAssets.I_TO_BATTLE_MAIN,
                key="page_act->page_act_ap",
            )
        # 体力爬塔进入是门票则切换
        page_act_ap.add_enter_failure_hooks(
            pages.conditional_action(
                condition=all_of(
                    ActivityShikigamiAssets.I_CLIMB_MODE_PASS,
                    ActivityShikigamiAssets.I_ACT_FIRE,
                ),
                action=ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH,
            )
        )
        if flag:
            # 门票爬塔和中转界面关联
            page_act_map.connect(
                page_act_pass,
                ActivityShikigamiAssets.I_MAP_GOTO_BATTLE,
                key="page_act_map->page_act_pass",
            )
        else:
            # 门票爬塔和主界面关联
            page_act.connect(
                page_act_pass,
                ActivityShikigamiAssets.I_TO_BATTLE_MAIN,
                key="page_act->page_act_pass",
            )
        # 门票爬塔进入是体力则切换
        page_act_pass.add_enter_failure_hooks(
            pages.conditional_action(
                condition=ActivityShikigamiAssets.I_CLIMB_MODE_AP,
                action=ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH,
            )
        )
        # 门票和体力互相切换
        page_act_pass.connect(
            page_act_ap,
            ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH,
            key="page_act_pass->page_act_ap",
        )
        page_act_ap.connect(
            page_act_pass,
            ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH,
            key="page_act_ap->page_act_pass",
        )

    def lock_team(self, battle_conf: GeneralBattleConfig):
        enable = battle_conf.lock_team_enable
        match self.climb_type:
            case "boss":
                lock_rule = self.I_LOCK
                unlock_rule = self.I_UNLOCK
            case _:
                lock_rule = self.I_AP_LOCK
                unlock_rule = self.I_AP_UNLOCK
        if enable:
            logger.info("正在确认活动阵容已锁定")
            click_rule, stop_rule = unlock_rule, lock_rule
        else:
            logger.info("正在确认活动阵容已解锁")
            click_rule, stop_rule = lock_rule, unlock_rule
        timer = Timer(12).start()
        while True:
            self.screenshot()
            if self.appear(stop_rule):
                return
            if timer.reached():
                raise GameStuckError("无法确认活动阵容锁定状态，请检查阵容开关")
            self.appear_then_click(click_rule, interval=1.5)
