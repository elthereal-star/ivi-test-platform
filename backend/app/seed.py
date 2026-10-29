"""演示种子数据。

刻意把数据造成「有故事」的形态：
- 三个批次递进，v1.3.0.0 出现明显回归（NAVI/POI/BT 由通过变失败）
- 失败签名共用同一根因，聚类后 5 条失败归成 1 簇，说明聚类有用
- 压测 v1.3.0.0 的 MTBF 比上一版差，能直接看图讲结论
"""

import random
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.core.db import engine
from app.core.security import hash_password
from app.models import (
    AiDraft,
    ExecSource,
    ExecStatus,
    Execution,
    IncidentType,
    Module,
    PlanStatus,
    StabilityIncident,
    StabilityRun,
    TestCase,
    TestPlan,
    User,
)
from app.services import clustering
from app.services.ai import fallback_cases

MODULES = [
    ("VOICE", "AI语音", 10),
    ("NAVI", "导航", 20),
    ("POI", "POI搜索", 30),
    ("ROUTE", "路线规划", 40),
    ("CLUSTER", "仪表显示", 50),
    ("BT", "蓝牙电话", 60),
    ("MEDIA", "多媒体", 70),
    ("SETTING", "系统设置", 80),
]

# (code, module, priority, title, precondition, [(action, expected)], expected, tags)
CASES: list[tuple[str, str, str, str, str, list[tuple[str, str]], str, list[str]]] = [
    ("VOICE-001", "VOICE", "P0", "语音唤醒响应时延不大于 1.5 秒", "车机已开机，语音助手待唤醒，环境噪音低于 45dB",
     [("说“你好小牛”并计时", "界面 1.5 秒内出现聆听动效"), ("说“今天天气怎么样”", "1.5 秒内开始播报")],
     "唤醒与首字响应均在阈值内", ["冒烟", "性能"]),
    ("VOICE-002", "VOICE", "P1", "唤醒后 3 秒无指令自动退出聆听态", "语音助手已激活",
     [("唤醒后保持静默 5 秒", "3 秒时退出聆听态并给出提示音")], "无指令时自动退出，不常驻占用麦克风", ["主流程"]),
    ("VOICE-003", "VOICE", "P0", "语音“导航到指定地点”正确跳转导航", "网络正常，导航服务可用",
     [("说“导航到武汉纺织大学”", "解析出唯一目的地"), ("确认开始导航", "进入导航页面并开始播报")],
     "语音意图被正确解析并进入导航", ["冒烟", "联动"]),
    ("VOICE-004", "VOICE", "P2", "带川渝口音的普通话指令识别", "环境安静，测试人员为川渝口音",
     [("用川渝口音说“打开空调”", "识别成功率不低于 80%")], "方言口音下仍可正确识别常用指令", ["兼容性"]),
    ("VOICE-005", "VOICE", "P1", "弱网下语音识别失败的提示与重试", "将网络限速至 200kbps",
     [("说“播放周杰伦的歌”", "5 秒内提示网络异常"), ("恢复网络后重试同一指令", "正常执行")],
     "弱网下有明确提示，恢复后可重试", ["异常场景"]),
    ("VOICE-006", "VOICE", "P1", "播报过程中再次唤醒可打断当前播报", "正在播报导航指引",
     [("播报中说“你好小牛”", "立即停止播报并进入聆听态"), ("说“继续导航”", "恢复原播报")],
     "支持打断且状态一致", ["交互"]),
    ("VOICE-007", "VOICE", "P2", "车速变化时语音播报音量自适应", "车辆可模拟不同车速",
     [("车速 0km/h 时记录音量", "音量基准值 A"), ("车速提升至 80km/h", "音量明显高于 A 且不破音")],
     "音量随车速提升，差值可感知且不失真", ["体验"]),
    ("VOICE-008", "VOICE", "P1", "连续两条指令不丢失", "语音助手已激活",
     [("连续说“打开车窗”“关闭车窗”", "两条指令依次生效"), ("查看日志", "两条意图均被解析")],
     "连续指令无遗漏、顺序正确", ["并发"]),

    ("NAVI-001", "NAVI", "P1", "首次导航起点为当前定位位置", "GPS 已定位，定位精度小于 10 米",
     [("发起任意目的地导航", "起点显示为当前所在道路")], "起点与实车位置一致", ["主流程"]),
    ("NAVI-002", "NAVI", "P0", "偏航后 5 秒内自动重新规划路线", "已进入导航，路线已规划",
     [("驶离规划路线 50 米以上", "5 秒内提示重新规划并给出新路线")], "偏航重算及时，路线合理", ["冒烟", "核心"]),
    ("NAVI-003", "NAVI", "P1", "导航中接听来电后恢复导航状态", "已连接蓝牙，可正常呼入",
     [("导航进行中接听来电", "通话界面浮层显示，导航继续后台运行"), ("挂断电话", "回到导航界面，指引连续")],
     "通话前后导航状态连续，不丢失路线", ["中断恢复"]),
    ("NAVI-004", "NAVI", "P2", "隧道内 GPS 丢失时的惯性导航表现", "路线包含长度大于 1km 的隧道",
     [("驶入隧道直至 GPS 丢失", "提示信号弱，界面保持指引"), ("驶出隧道", "10 秒内恢复定位")],
     "隧道内不跳变，出隧道可快速恢复", ["弱信号"]),
    ("NAVI-005", "NAVI", "P1", "目的地模糊匹配给出候选列表", "网络正常",
     [("输入“大学”", "给出附近 5 公里内候选列表"), ("选择第 2 条", "路线规划以该条为终点")],
     "模糊输入可给出候选并可选中", ["搜索"]),
    ("NAVI-006", "NAVI", "P1", "退出导航后仪表指引信息清除", "导航进行中，仪表正常显示",
     [("点击退出导航", "仪表指引箭头与剩余里程在 2 秒内消失")], "仪表无残留指引", ["联动"]),
    ("NAVI-007", "NAVI", "P2", "500 公里以上长途路线规划耗时", "网络正常",
     [("规划约 600 公里路线", "10 秒内返回结果"), ("切换备选路线", "2 秒内完成切换")],
     "长途规划耗时在阈值内", ["性能"]),

    ("POI-001", "POI", "P1", "模糊关键词返回附近 POI 结果", "网络正常，已授权定位",
     [("搜索“加油站”", "返回 10 公里内结果，按距离升序")], "结果相关且排序正确", ["主流程"]),
    ("POI-002", "POI", "P1", "POI 详情页点击电话拉起蓝牙拨号", "已连接蓝牙手机",
     [("进入任一 POI 详情", "显示电话号码"), ("点击电话图标", "拉起拨号界面并带出号码")],
     "跳转拨号正确，号码无截断", ["联动"]),
    ("POI-003", "POI", "P2", "搜索结果分页加载更多", "搜索结果多于 20 条",
     [("滑动到底部", "自动加载下一页且无重复项")], "分页无重复、无漏项", ["列表"]),
    ("POI-004", "POI", "P1", "无网络时搜索给出明确提示", "关闭车机数据网络",
     [("搜索“停车场”", "2 秒内提示无网络"), ("恢复网络后重试", "正常返回结果")],
     "无网提示明确，无白屏或无限加载", ["异常场景"]),
    ("POI-005", "POI", "P3", "搜索历史去重且最多保留 10 条", "已有搜索历史",
     [("重复搜索同一关键词 3 次", "历史中仅保留 1 条"), ("累计搜索 12 个不同关键词", "仅保留最近 10 条")],
     "历史去重与上限均生效", ["边界"]),
    ("POI-006", "POI", "P2", "搜索结果距离与实车位置一致", "GPS 已定位",
     [("对比首条结果距离与地图测距", "误差不超过 100 米")], "距离计算准确", ["准确性"]),

    ("ROUTE-001", "ROUTE", "P1", "途经点添加、删除与顺序调整", "已规划一条路线",
     [("添加 2 个途经点", "地图按顺序连线"), ("拖动调整顺序", "路线重算且里程更新")],
     "途经点增删改均正确生效", ["主流程"]),
    ("ROUTE-002", "ROUTE", "P2", "避开拥堵模式下的时间对比", "路况数据可用",
     [("分别以默认与避开拥堵模式规划", "两种模式预计时间与里程均有差异")], "模式差异可感知且合理", ["策略"]),
    ("ROUTE-003", "ROUTE", "P1", "多路线方案切换后指引同步", "已返回 3 条备选路线",
     [("切换到第 2 条路线", "地图与指引同步更新"), ("开始导航", "按第 2 条路线播报")],
     "切换后指引与地图一致", ["交互"]),
    ("ROUTE-004", "ROUTE", "P2", "无路可达时的失败提示", "目的地设为海岛等不可达点",
     [("发起规划", "提示无法规划并给出原因")], "失败提示清晰，不卡在加载态", ["异常场景"]),

    ("CLUSTER-001", "CLUSTER", "P0", "仪表档位显示与实车档位一致", "车辆可切换 P/R/N/D 档",
     [("依次切换四个档位", "仪表档位字符同步变化且无延迟"), ("切换至 R 档", "倒车影像同时弹出")],
     "档位显示准确无延迟", ["冒烟", "安全"]),
    ("CLUSTER-002", "CLUSTER", "P1", "SOC 电量显示精度与充放电一致性", "电池 SOC 可读取",
     [("静置 10 分钟后读取仪表 SOC", "与后台读数偏差不超过 1%"), ("放电 5% 后复查", "偏差仍不超过 1%")],
     "SOC 显示精度满足要求", ["准确性"]),
    ("CLUSTER-003", "CLUSTER", "P0", "告警图标点亮与熄灭时机正确", "可注入各类告警信号",
     [("注入低电量告警", "3 秒内图标点亮并播报"), ("解除告警", "5 秒内图标熄灭")],
     "告警响应及时，无误报漏报", ["冒烟", "安全"]),
    ("CLUSTER-004", "CLUSTER", "P2", "夜间模式亮度随环境光自动调节", "可模拟环境光变化",
     [("环境光由 500lux 降至 10lux", "仪表亮度平滑下降，无跳变")], "亮度调节平滑可读", ["体验"]),
    ("CLUSTER-005", "CLUSTER", "P1", "仪表与小计里程与中控同步", "已完成一段行驶",
     [("对比仪表与中控总里程", "数值完全一致")], "双端里程一致", ["联动"]),
    ("CLUSTER-006", "CLUSTER", "P2", "开机自检动画完整播放", "冷启动车机",
     [("上电启动", "自检动画完整播放一次且不卡顿")], "自检动画完整无跳帧", ["启动"]),

    ("BT-001", "BT", "P1", "首次蓝牙配对流程", "手机蓝牙已开启，车机处于可发现状态",
     [("手机搜索并配对", "配对码一致后连接成功"), ("断开后重新连接", "自动回连成功")],
     "配对与回连均成功", ["主流程"]),
    ("BT-002", "BT", "P1", "来电显示联系人姓名", "通讯录已同步",
     [("用已存联系人呼入", "显示姓名与号码")], "联系人姓名正确显示", ["主流程"]),
    ("BT-003", "BT", "P2", "通话中切换音频声道", "通话进行中",
     [("切换至手机听筒", "车机扬声器静音，手机出声")], "声道切换生效且可切回", ["交互"]),
    ("BT-004", "BT", "P1", "超出范围断开后自动重连", "已连接蓝牙",
     [("携带手机离开 15 米以上", "车机提示断开"), ("返回车内", "30 秒内自动重连")],
     "断开提示明确，回连及时", ["异常场景"]),
    ("BT-005", "BT", "P2", "通讯录同步 500 条上限", "手机通讯录多于 500 条",
     [("执行通讯录同步", "同步条数达到上限并提示"), ("搜索第 501 条联系人", "明确提示超出上限")],
     "上限处理有提示，不静默截断", ["边界"]),

    ("MEDIA-001", "MEDIA", "P1", "U 盘插入识别与播放", "U 盘含 mp3 与 flac 文件",
     [("插入 U 盘", "5 秒内识别并进入媒体源"), ("播放 flac 文件", "正常出声无卡顿")],
     "U 盘识别与多格式播放正常", ["主流程"]),
    ("MEDIA-002", "MEDIA", "P1", "蓝牙音乐切歌与进度同步", "已通过蓝牙连接手机",
     [("车机端点击下一首", "手机端同步切换，车机显示新歌名")], "双端状态同步", ["联动"]),
    ("MEDIA-003", "MEDIA", "P2", "播放中拔出 U 盘的异常处理", "正在播放 U 盘音乐",
     [("直接拔出 U 盘", "3 秒内提示媒体源移除并停止播放")], "无崩溃、无残留播放状态", ["异常场景"]),
    ("MEDIA-004", "MEDIA", "P3", "均衡器设置重启后记忆", "已调整均衡器参数",
     [("重启车机", "均衡器参数保持上次设置")], "设置项持久化", ["持久化"]),

    ("SETTING-001", "SETTING", "P1", "中英文语言切换后全局生效", "系统支持中文与英文",
     [("切换为英文", "所有界面文案切换，无中文残留"), ("切回中文", "文案全部恢复")],
     "语言切换完整生效", ["主流程"]),
    ("SETTING-002", "SETTING", "P1", "恢复出厂设置后账号自动登出", "已登录账号",
     [("执行恢复出厂设置", "重启后账号为未登录态，个人数据清空")], "数据清除彻底", ["安全"]),
    ("SETTING-003", "SETTING", "P2", "日夜主题切换与跟随", "系统主题可设置",
     [("设置跟随系统并切换至夜间", "界面配色同步变化")], "主题切换无闪屏", ["体验"]),
    ("SETTING-004", "SETTING", "P1", "OTA 升级过程中断电后的恢复", "可对车机断电",
     [("升级至 50% 时断电", "重新上电后进入恢复流程并提示重试"), ("重新升级", "升级成功且版本号正确")],
     "断电后可恢复，不砖机", ["异常场景", "高风险"]),
    ("SETTING-005", "SETTING", "P3", "屏幕亮度设置记忆", "已手动调整亮度",
     [("重启车机", "亮度保持上次设置")], "亮度设置持久化", ["持久化"]),
]

FAIL_SIGNATURES = {
    "NAVI": (
        "com.amap.api.services.core.AMapException: 网络请求失败, code=12, "
        "at com.niu.navi.RouteClient.query(RouteClient.java:88)"
    ),
    "POI": "com.amap.api.services.core.AMapException: 网络请求失败, code=12",
    "VOICE": (
        "java.lang.NullPointerException: Cannot invoke \"String.length()\" because \"asrText\" is null "
        "at com.niu.voice.AsrEngine.onResult(AsrEngine.java:137)"
    ),
    "CLUSTER": "android.os.DeadObjectException: binder died while updating cluster display service",
    "BT": "java.lang.IllegalStateException: BluetoothAdapter is off while dialing",
    "MEDIA": "android.media.MediaPlayer$PlaybackException: error (1, -1004)",
    "ROUTE": "com.amap.api.services.core.AMapException: 网络请求失败, code=12",
    "SETTING": "android.content.ActivityNotFoundException: unable to find explicit activity class",
}


def _users(session: Session) -> list[User]:
    rows = [
        ("admin@ivi-test.com", "系统管理员", "admin", "Admin@12345"),
        ("lead@ivi-test.com", "测试负责人", "lead", "Lead@12345"),
        ("qa@ivi-test.com", "执行测试员", "executor", "Qa@12345"),
        ("viewer@ivi-test.com", "只读访客", "viewer", "Viewer@12345"),
    ]
    users = [
        User(email=e, full_name=n, role=r, hashed_password=hash_password(p)) for e, n, r, p in rows
    ]
    for u in users:
        session.add(u)
    session.flush()
    return users


def _modules(session: Session) -> dict[str, Module]:
    mods = {}
    for code, name, sort in MODULES:
        m = Module(code=code, name=name, sort=sort)
        session.add(m)
        mods[code] = m
    session.flush()
    return mods


def _cases(session: Session, mods: dict[str, Module], author: User) -> list[TestCase]:
    out = []
    for code, mod, pri, title, pre, steps, expected, tags in CASES:
        steps_data = [{"no": i, "action": a, "expected": e} for i, (a, e) in enumerate(steps, start=1)]
        c = TestCase(
            code=code,
            title=title,
            module_id=mods[mod].id,
            priority=pri,
            case_type="function",
            precondition=pre,
            steps=steps_data,
            expected=expected,
            tags=tags,
            created_by=author.id,
        )
        session.add(c)
        out.append(c)
    session.flush()
    return out


def _plans(session: Session, cases: list[TestCase], owner: User, qa: User) -> None:
    rng = random.Random(20261029)
    now = datetime.now(UTC)

    defs = [
        ("R2026.09-W1", "1.2.0.3 回归（第 1 周）", "1.2.0.3", PlanStatus.COMPLETED, 50, 0.70),
        ("R2026.10-W1", "1.2.1.0 回归（第 1 周）", "1.2.1.0", PlanStatus.COMPLETED, 30, 0.86),
        ("R2026.10-W3", "1.3.0.0 回归（第 3 周）", "1.3.0.0", PlanStatus.RUNNING, 3, 0.68),
    ]
    new_fail = {"NAVI-002", "NAVI-003", "POI-002", "VOICE-006", "BT-004"}
    fixed = {"CLUSTER-003", "MEDIA-003"}
    # 上一版失败、这一版修复的用例：必须在 W1 里是 FAIL，否则「已修复」列表是随机的
    to_fix_in_w3 = {"CLUSTER-003", "MEDIA-003"}
    # 本批次还没跑到的用例（真实场景：周期没走完）
    pending = {
        "SETTING-001", "SETTING-002", "SETTING-003", "SETTING-004", "SETTING-005",
        "ROUTE-003", "ROUTE-004", "VOICE-008", "MEDIA-004",
    }

    for code, name, fw, status, days_ago, base_rate in defs:
        created = now - timedelta(days=days_ago)
        plan = TestPlan(
            code=code,
            name=name,
            fw_version=fw,
            device_model="D21x",
            device_sn="SN2026000123",
            status=status,
            owner_id=owner.id,
            started_at=created,
            finished_at=created + timedelta(days=2) if status == PlanStatus.COMPLETED else None,
        )
        session.add(plan)
        session.flush()

        for case in cases:
            roll = rng.random()
            rate = base_rate + (0.10 if case.priority == "P0" else 0.0)
            if code == "R2026.10-W3" and case.code in new_fail:
                st = ExecStatus.FAIL
            elif code == "R2026.10-W1" and case.code in to_fix_in_w3:
                st = ExecStatus.FAIL
            elif code == "R2026.10-W3" and case.code in fixed:
                st = ExecStatus.PASS
            elif roll < rate:
                st = ExecStatus.PASS
            elif roll < rate + 0.04:
                st = ExecStatus.BLOCKED
            elif roll < rate + 0.06:
                st = ExecStatus.SKIP
            else:
                st = ExecStatus.FAIL

            if status == PlanStatus.RUNNING and case.code in pending:
                st = ExecStatus.NOT_RUN

            exec_ = Execution(plan_id=plan.id, case_id=case.id, status=st, source=ExecSource.MANUAL)
            if st not in (ExecStatus.NOT_RUN, ExecStatus.SKIP):
                exec_.executor_id = qa.id
                exec_.duration_s = rng.randint(40, 600)
                # 让执行时间落在批次开始后的两天内，散开一点更像真实记录
                exec_.executed_at = created + timedelta(minutes=rng.randint(30, 2800))
                exec_.attempts = 1
            if st == ExecStatus.FAIL:
                sig = FAIL_SIGNATURES.get(case.code.split("-")[0], "")
                exec_.error_signature = sig
                exec_.cluster_key = clustering.normalize_signature(clustering.split_lines(sig)) if sig else ""
                exec_.actual_result = "实际表现与预期不一致，详见日志"
                exec_.log_excerpt = sig[:400]
            elif st == ExecStatus.BLOCKED:
                exec_.actual_result = "环境不具备，未完成验证"
            session.add(exec_)
    session.flush()


def _stability(session: Session, mods: dict[str, Module], owner: User) -> None:
    rng = random.Random(7)
    now = datetime.now(UTC)

    runs = [
        ("STAB-2026-09", "1.2.1.0 连续 72 小时稳定性", "1.2.1.0", 72, 1440, 3, 2, 1, 0, 5, 1),
        ("STAB-2026-10", "1.3.0.0 连续 48 小时稳定性", "1.3.0.0", 48, 940, 7, 4, 2, 1, 9, 5),
    ]
    types = [IncidentType.CRASH, IncidentType.ANR, IncidentType.HANG, IncidentType.REBOOT]
    descs = {
        IncidentType.CRASH: "语音服务进程异常退出，界面闪回桌面",
        IncidentType.ANR: "导航主线程阻塞，弹出无响应对话框",
        IncidentType.HANG: "系统界面整体卡死，触摸无响应",
        IncidentType.REBOOT: "仪表黑屏后自动重启",
    }
    mod_codes = ["VOICE", "NAVI", "POI", "CLUSTER", "BT", "MEDIA"]

    for code, name, fw, hours, cycles, crash, anr, hang, reboot, auto_r, manual_r in runs:
        end = now - timedelta(days=3)
        start = end - timedelta(hours=hours)
        run = StabilityRun(
            code=code,
            name=name,
            fw_version=fw,
            device_sn="SN2026000123",
            start_at=start,
            end_at=end,
            planned_hours=hours,
            cycles_done=cycles,
            crash_count=crash,
            anr_count=anr,
            hang_count=hang,
            reboot_count=reboot,
            auto_recover_count=auto_r,
            manual_recover_count=manual_r,
            notes="台架压测，循环执行「语音唤醒-导航-切歌」脚本",
            created_by=owner.id,
        )
        session.add(run)
        session.flush()

        total = crash + anr + hang + reboot
        for i in range(total):
            it = types[i % len(types)]
            mod = mods[rng.choice(mod_codes)]
            occurred = start + timedelta(hours=rng.uniform(0.5, hours - 0.5))
            recovered = rng.random() < 0.85
            session.add(
                StabilityIncident(
                    run_id=run.id,
                    incident_type=it,
                    module_id=mod.id,
                    occurred_at=occurred,
                    description=descs[it],
                    log_excerpt=FAIL_SIGNATURES.get(mod.code, "")[:300],
                    recover_s=rng.randint(8, 240) if recovered else None,
                    recovered=recovered,
                )
            )


def _ai_draft(session: Session, mods: dict[str, Module], author: User) -> None:
    req = "语音助手应支持在导航播报过程中被唤醒打断，并能在打断后继续原导航；弱网时需给出明确提示"
    cases = fallback_cases(mods["VOICE"].name, req, 5, "P1")
    session.add(
        AiDraft(
            module_id=mods["VOICE"].id,
            requirement=req,
            count=5,
            model_name="rule-template",
            fallback=True,
            cases=cases,
            created_by=author.id,
        )
    )


def seed_if_empty() -> None:
    with Session(engine) as session:
        if session.exec(select(User)).first():
            return
        users = _users(session)
        mods = _modules(session)
        cases = _cases(session, mods, users[0])
        _plans(session, cases, users[1], users[2])
        _stability(session, mods, users[1])
        _ai_draft(session, mods, users[0])
        session.commit()
