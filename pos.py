Debug=False
def prinput(i):
    if Debug==True:
        input(i)
    elif Debug==False:
        print(i)

import time
import datetime
import random
import pyautogui
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False
import cv2
import numpy as np
from pynput import keyboard as pynput_keyboard
import sys
import os
import json
import pygame
import threading
import ctypes

# ===================== 新增：管理员权限检测与提权 =====================
def is_admin():
    """检测当前进程是否拥有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员身份重新启动程序"""
    print("=" * 50)
    prinput("检测到当前无管理员权限，正在尝试提权...")
    print(f"程序路径：{sys.executable}")
    print(f"脚本路径：{__file__}")
    print("=" * 50)
    
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{__file__}"', None, 1)
        print("提权请求已发送，请在弹出的UAC窗口中点击【是】确认！")
        sys.exit(0)
    except Exception as e:
        print(f"提权失败！错误信息：{str(e)}")
        input("按Enter键退出程序...")
        sys.exit(1)

# ===================== 原有逻辑 =====================
pygame.init()
pygame.display.set_caption('POS')
window_width, window_height = 1280, 720
screen = pygame.display.set_mode((window_width, window_height), pygame.RESIZABLE)
clock = pygame.time.Clock()

# 配置默认参数
wait_minutes = (15, 25)
method2_probability = 0.25
vip_probability = 0.2
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)
LIGHT_BLUE = (173, 216, 230)
font = pygame.font.SysFont('Microsoft YaHei', 24)
font_small = pygame.font.SysFont('Microsoft YaHei', 18)

base_dir = os.path.dirname(os.path.abspath(__file__))

# ===================== 识图工具函数 =====================
_IMG_CONF = 0.95

_ICON_NAME_MAP = {
    '会员': 'member',
    '确定': 'confirm',
    '清除': 'clear',
    '获取会员信息失败': 'vip_fail',
    '确认收款': 'confirm_payment',
    '现金': 'cash',
}

def _img_path(name):
    filename = _ICON_NAME_MAP.get(name, name) + '.png'
    pos_path = os.path.join(base_dir, 'POS', filename)
    if os.path.exists(pos_path):
        return pos_path
    return os.path.join(base_dir, 'assets', 'pos_icons', filename)

_img_cache = {}

def _load_template(name):
    if name not in _img_cache:
        path = _img_path(name)
        try:
            _img_cache[name] = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        except Exception:
            _img_cache[name] = None
    return _img_cache[name]

for _tn in _ICON_NAME_MAP:
    _load_template(_tn)

def _grab_screen():
    screenshot = pyautogui.screenshot()
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)

def _match_tmpl(screen_gray, tmpl_gray, confidence):
    result = cv2.matchTemplate(screen_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    if max_val >= confidence:
        th, tw = tmpl_gray.shape
        return (max_loc[0], max_loc[1], tw, th)
    return None

def _match_on_screen(screen_gray, name, confidence=_IMG_CONF):
    tmpl = _load_template(name)
    if tmpl is None:
        return None
    return _match_tmpl(screen_gray, tmpl, confidence)

def wait_for_image(name, timeout=10, confidence=_IMG_CONF, click=False, interval=0.1):
    deadline = time.time() + timeout if timeout > 0 else None
    while True:
        try:
            screen_gray = _grab_screen()
            loc = _match_on_screen(screen_gray, name, confidence)
            if loc is not None:
                if click:
                    pyautogui.click(loc[0] + loc[2] // 2, loc[1] + loc[3] // 2)
                return True, loc
        except Exception:
            pass
        if deadline and time.time() >= deadline:
            return False, None
        time.sleep(interval)

def image_on_screen(name, confidence=_IMG_CONF):
    try:
        screen_gray = _grab_screen()
        return _match_on_screen(screen_gray, name, confidence) is not None
    except Exception:
        return False

def click_image(name, confidence=_IMG_CONF):
    try:
        screen_gray = _grab_screen()
        loc = _match_on_screen(screen_gray, name, confidence)
        if loc is not None:
            pyautogui.click(loc[0] + loc[2] // 2, loc[1] + loc[3] // 2)
            return True
    except Exception:
        pass
    return False

def multi_detect(names, confidence=_IMG_CONF):
    result = {}
    try:
        screen_gray = _grab_screen()
        for name in names:
            tmpl = _load_template(name)
            if tmpl is None:
                result[name] = None
            else:
                result[name] = _match_tmpl(screen_gray, tmpl, confidence)
    except Exception:
        for name in names:
            result[name] = None
    return result

# ===================== 全局热键（pynput 版） =====================
_MOD_ALT = 0x0001

class _HotkeyListener:
    def __init__(self, hotkeys, callback):
        self.callback = callback
        self.hotkeys = hotkeys
        self._listener = None

    def start(self):
        try:
            bindings = {}
            for mod, vk in self.hotkeys:
                parts = []
                if mod & 0x0002:
                    parts.append('<ctrl>')
                if mod & 0x0001:
                    parts.append('<alt>')
                if mod & 0x0004:
                    parts.append('<shift>')
                if 0x41 <= vk <= 0x5A:
                    parts.append(chr(vk).lower())
                else:
                    _VK_NAME = {
                        0x70:'f1',0x71:'f2',0x72:'f3',0x73:'f4',
                        0x74:'f5',0x75:'f6',0x76:'f7',0x77:'f8',
                        0x78:'f9',0x79:'f10',0x7A:'f11',0x7B:'f12',
                    }
                    parts.append('<' + _VK_NAME.get(vk, hex(vk)) + '>')
                bindings['+'.join(parts)] = self.callback
            self._listener = pynput_keyboard.GlobalHotKeys(bindings)
            self._listener.daemon = True
            self._listener.start()
            print(f"全局热键已启动（pynput）: {list(bindings.keys())}")
        except Exception as e:
            print(f"热键启动失败: {e}")

    def stop(self):
        try:
            if self._listener:
                self._listener.stop()
        except Exception:
            pass

# ===================== 加载条码和VIP列表 =====================
barcode1_path = os.path.join(base_dir, '不能扫在线的条码.json')
barcode2_path = os.path.join(base_dir, '可以扫在线的条码.json')
with open(barcode1_path, 'r', encoding='utf-8') as f:
    METHOD1_BARCODES = json.load(f)
with open(barcode2_path, 'r', encoding='utf-8') as f:
    METHOD2_BARCODES = json.load(f)

VIP_list_path = os.path.join(base_dir, 'vip列表.json')
with open(VIP_list_path, 'r', encoding='utf-8') as f:
    VIP_list = json.load(f)

# ===================== 会员扫码记录 =====================
VIP_RECORD_PATH = os.path.join(base_dir, '会员扫码记录.json')

_vip_records_cache = None
_vip_records_mtime = 0

def _load_vip_records():
    global _vip_records_cache, _vip_records_mtime
    if os.path.exists(VIP_RECORD_PATH):
        try:
            mtime = os.path.getmtime(VIP_RECORD_PATH)
            if _vip_records_cache is not None and _vip_records_mtime == mtime:
                return _vip_records_cache
            with open(VIP_RECORD_PATH, 'r', encoding='utf-8') as f:
                _vip_records_cache = json.load(f)
                _vip_records_mtime = mtime
                return _vip_records_cache
        except Exception:
            pass
    _vip_records_cache = []
    return []

def _save_vip_records(records):
    global _vip_records_cache, _vip_records_mtime
    with open(VIP_RECORD_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    _vip_records_cache = records
    try:
        _vip_records_mtime = os.path.getmtime(VIP_RECORD_PATH)
    except Exception:
        pass

def _add_vip_record(vip):
    records = _load_vip_records()
    now = datetime.datetime.now()
    records.append({'vip': vip, 'time': now.strftime('%Y-%m-%d %H:%M:%S')})
    _save_vip_records(records)

def _get_unscanned_this_month():
    records = _load_vip_records()
    now = datetime.datetime.now()
    month_prefix = now.strftime('%Y-%m')
    scanned = set()
    for r in records:
        if r['time'].startswith(month_prefix):
            scanned.add(str(r['vip']))
    return [v for v in VIP_list if str(v) not in scanned]

# ===================== 加载图片 =====================
zoom = 1
def load_image(path, width, height):
    try:
        i = pygame.image.load(path)
        i = pygame.transform.smoothscale(i, (width * zoom, height * zoom))
    except:
        i = pygame.Surface((width * zoom, height * zoom))
        i.fill(LIGHT_BLUE)
    return i

class Img:
    quit = load_image(os.path.join(base_dir, "assets/gui/quit.png"), 100, 50)
    done = load_image(os.path.join(base_dir, "assets/gui/done.png"), 100, 50)
    save_vip = load_image(os.path.join(base_dir, "assets/gui/save_vip.png"), 100, 50)
    revise = load_image(os.path.join(base_dir, "assets/gui/revise.png"), 100, 50)
    immediately = load_image(os.path.join(base_dir, "assets/gui/immediately.png"), 100, 50)
    reset_time = load_image(os.path.join(base_dir, "assets/gui/reset_time.png"), 100, 50)

def highlight(button, pos, color=LIGHT_BLUE):
    if button.collidepoint(pos):
        pygame.draw.rect(screen, color, button, 3)

# ===================== Scanner 类 =====================
class Scanner:
    def __init__(self):
        # 布局：三块等间距排列
        # 每块结构：标题(30) + 间隔(10) + 预设按钮行1(50) + 间隔(10) + [预设按钮行2(50) + 间隔(10)] + 自定义标签(30) + 间隔(5) + 输入框(40)
        # 块1(2行预设): 30+10+50+10+50+10+30+5+40 = 235
        # 块2/3(1行预设): 30+10+50+10+30+5+40 = 175
        # 块间间隔 = 30

        # 块1: 扫码间隔 (起始 y=20)
        self.扫码间隔s = []
        for i in range(8):
            if i < 4:
                self.扫码间隔s.append([pygame.Rect(100 + i * 150, 60, 100, 50), (5 + i * 5, 15 + i * 5)])
            else:
                self.扫码间隔s.append([pygame.Rect(100 + (i - 4) * 150, 120, 100, 50), (5 + i * 5, 15 + i * 5)])

        # 块2: 方法2概率 (起始 y=20+235+30=285)
        self.方法2概率s = []
        for i in range(5):
            self.方法2概率s.append([pygame.Rect(100 + i * 150, 325, 100, 50), i * 0.25])

        # 块3: VIP概率 (起始 y=285+175+30=490)
        self.VIP概率s = []
        for i in range(5):
            self.VIP概率s.append([pygame.Rect(100 + i * 150, 530, 100, 50), i * 0.25])

        a = 1150
        self.quit_button = pygame.Rect(a, 640, 100, 50)
        self.done_button = pygame.Rect(a - 150 * 0, 590, 100, 50)
        self.revise_button = pygame.Rect(a - 150 * 1, 640, 100, 50)
        self.immediately_button = pygame.Rect(a - 150 * 2, 640, 100, 50)
        self.reset_time_button = pygame.Rect(a - 150 * 3, 640, 100, 50)
        self.record_button = pygame.Rect(a - 150 * 4, 640, 100, 50)

        # 自定义输入框
        self.input_boxes = {}
        self.input_active = None
        self.input_texts = {}
        self.input_boxes['wait_min'] = pygame.Rect(380, 180, 80, 40)   # 块1输入框 y=180
        self.input_texts['wait_min'] = ''
        self.input_boxes['wait_max'] = pygame.Rect(510, 180, 80, 40)
        self.input_texts['wait_max'] = ''
        self.input_boxes['prob'] = pygame.Rect(380, 395, 80, 40)       # 块2输入框 y=395
        self.input_texts['prob'] = ''
        self.input_boxes['vip_prob'] = pygame.Rect(380, 600, 80, 40)   # 块3输入框 y=600
        self.input_texts['vip_prob'] = ''

        self.record_scroll = 0
        self.record_tab = 0

        self.wait_time = 10
        self.next_time = datetime.datetime.now() + datetime.timedelta(seconds=self.wait_time)
        self.previous_barcode = '无'
        self.previous_vip = '无'
        self.previous_method = '无'

        self.lock = threading.Lock()

        self.key_listener = _HotkeyListener([(_MOD_ALT, 0x58)], self.on_hotkey_press)
        self.key_listener.start()

    def on_hotkey_press(self):
        with self.lock:
            print("检测到Alt+X全局快捷键，执行立即扫码")
            if not self.scan_the_barcode():
                print("扫码失败，等待下一次扫码")
            self.wait_time, self.next_time = self.get_wait_time_and_next_time()

    def get_wait_time_and_next_time(self):
        """扫码间隔不需要在预设值基础上上下浮动"""
        wait_time = random.randint(wait_minutes[0] * 60, wait_minutes[1] * 60)
        next_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
        return wait_time, next_time

    def select_vip_balanced(self):
        """平均扫VIP算法：优先选择本月未扫的会员，确保每月每人至少一次
        返回选中的vip编号，如果VIP列表为空则返回None"""
        global VIP_list
        if not VIP_list:
            return None
        unscanned = _get_unscanned_this_month()
        if unscanned:
            # 还有本月未扫的，优先从中随机选
            chosen = random.choice(unscanned)
            print(f"平均算法：从{len(unscanned)}个未扫会员中选择 {chosen}")
            return chosen
        else:
            # 本月全部已扫过一轮，选择扫得最少的一个
            records = _load_vip_records()
            now = datetime.datetime.now()
            month_prefix = now.strftime('%Y-%m')
            # 统计本月每个vip被扫次数
            vip_count = {}
            for v in VIP_list:
                vip_count[str(v)] = 0
            for r in records:
                if r['time'].startswith(month_prefix):
                    key = str(r['vip'])
                    if key in vip_count:
                        vip_count[key] += 1
            # 找扫得最少的
            min_count = min(vip_count.values())
            candidates = [v for v, c in vip_count.items() if c == min_count]
            chosen = random.choice(candidates)
            print(f"平均算法：本月已全部扫过，从扫得最少({min_count}次)的{len(candidates)}人中选 {chosen}")
            return chosen

    def select_barcode(self, method):
        if method == 2:
            return random.choice(METHOD2_BARCODES)
        else:
            return random.choice(METHOD1_BARCODES)

    def ensure_focus(self):
        print("检测'会员'图标以确定界面已打开...")
        found, _ = wait_for_image('会员', timeout=10)
        if found:
            print("检测到'会员'图标，界面已就绪")
            return True
        print("未检测到'会员'图标，界面可能未打开")
        return False

    def scan_the_barcode(self):
        global vip_probability
        try:
            print("唤醒界面（Alt+Z）...")
            for i in range(3):
                pyautogui.keyDown('alt')
                pyautogui.press('z')
                pyautogui.keyUp('alt')
                time.sleep(random.uniform(0.2, 0.4))

            # 等待界面打开（同时检测'会员'/'确认收款'/'现金'图标），30秒超时
            wakeup_deadline = time.time() + 30
            while time.time() < wakeup_deadline:
                # 用 multi_detect 一次性检测三个图标
                detected = multi_detect(['会员', '确认收款', '现金'])
                
                if detected['会员']:
                    print("界面已打开（检测到'会员'图标）")
                    break
                
                # 如果同时检测到'确认收款'和'现金'，说明有未完成的收款需要处理
                if detected['确认收款'] and detected['现金']:
                    print("检测到'确认收款'和'现金'图标，先完成收款操作...")
                    # 先点击'现金'
                    clicked_cash = click_image('现金')
                    time.sleep(random.uniform(0.3, 0.5))
                    # 再点击'确认收款'
                    clicked_payment = click_image('确认收款')
                    time.sleep(random.uniform(0.3, 0.5))
                    
                    if clicked_cash and clicked_payment:
                        print("收款操作完成，确认POS已启动")
                    else:
                        print("收款操作部分失败（现金=%s, 确认收款=%s），继续流程" % (clicked_cash, clicked_payment))
                    
                    # 短暂等待后再次检测'会员'图标以确认POS界面已就绪
                    time.sleep(random.uniform(0.3, 0.6))
                    recheck = multi_detect(['会员'])
                    if recheck['会员']:
                        print("再次确认：检测到'会员'图标，POS已就绪")
                    else:
                        print("再次确认：未检测到'会员'图标，但收款已处理，继续流程")
                    break
                
                print("未检测到'会员'/'确认收款'+'现金'图标，重试唤醒...")
                pyautogui.keyDown('alt')
                pyautogui.press('z')
                pyautogui.keyUp('alt')
                time.sleep(random.uniform(0.3, 0.6))
            else:
                print("超时：未检测到'会员'或'确认收款'+'现金'图标，放弃本次扫码")
                return False

            time.sleep(random.uniform(0.3, 0.6))

            method = 1
            if random.random() < method2_probability:
                method = 2
            self.previous_method = method

            barcode = self.select_barcode(method)
            self.previous_barcode = barcode
            pyautogui.write(barcode, interval=0)
            print(f"输入条码: {barcode}")
            time.sleep(random.uniform(0.3, 0.6))

            pyautogui.press('enter')
            time.sleep(random.uniform(0.3, 0.6))

            confirm_key = 'f6' if method == 2 else 'enter'
            print(f"确认键: {confirm_key}")

            vip_i = False
            if random.random() < vip_probability and len(VIP_list) > 0 and confirm_key == 'enter':
                vip_i = True
            else:
                vip_probability = 0.5

            if vip_i:
                vip_probability -= 0.1
                vip = self.select_vip_balanced()
                if vip is None:
                    print("VIP列表为空，跳过VIP扫码")
                    vip_i = False
                else:
                    self.previous_vip = vip
                    time.sleep(random.uniform(0.3, 0.6))

                print("点击'会员'图标打开VIP窗口...")
                vip_window_deadline = time.time() + 20
                while time.time() < vip_window_deadline:
                    clicked = click_image('会员')
                    if clicked:
                        break
                    print("未找到'会员'图标，重试...")
                    time.sleep(random.uniform(0.2, 0.4))
                else:
                    print("超时：未找到'会员'图标，放弃本次扫码")
                    return False

                print("等待会员窗口打开（检测'确定'图标）...")
                vip_confirm_deadline = time.time() + 20
                while time.time() < vip_confirm_deadline:
                    found, _ = wait_for_image('确定', timeout=5)
                    if found:
                        print("会员窗口已打开（检测到'确定'图标）")
                        break
                    print("未检测到'确定'图标，重试点击'会员'...")
                    click_image('会员')
                    time.sleep(random.uniform(0.3, 0.6))
                else:
                    print("超时：未检测到'确定'图标，放弃本次扫码")
                    return False

                time.sleep(random.uniform(0.3, 0.6))

                vip_str = "000" + str(vip)
                pyautogui.write(vip_str, interval=0)
                print(f"输入会员码: {vip_str}")
                time.sleep(random.uniform(0.3, 0.5))

                print("点击'确定'提交会员码...")
                submit_deadline = time.time() + 15
                while time.time() < submit_deadline:
                    clicked = click_image('确定')
                    if clicked:
                        break
                    print("未找到'确定'图标，重试...")
                    time.sleep(random.uniform(0.2, 0.4))
                else:
                    print("超时：未找到'确定'图标，放弃本次扫码")
                    return False

                print("等待会员信息加载（检测'清除'或'获取会员信息失败'）...")
                info_deadline = time.time() + 20
                vip_loaded = False
                while time.time() < info_deadline:
                    detected = multi_detect(['清除', '获取会员信息失败'])
                    if detected['清除']:
                        print("检测到'清除'图标，会员信息已加载")
                        _add_vip_record(vip)
                        print(f"已记录会员码: {vip}")
                        vip_loaded = True
                        break
                    if detected['获取会员信息失败']:
                        print("检测到'获取会员信息失败'，点击'确定'跳过")
                        fail_confirm_deadline = time.time() + 10
                        while time.time() < fail_confirm_deadline:
                            if click_image('确定'):
                                break
                            time.sleep(random.uniform(0.2, 0.4))
                        else:
                            print("超时：未找到'确定'图标（失败弹窗），放弃本次扫码")
                            return False
                        self.previous_vip = '失败'
                        vip_loaded = True
                        break
                    # 额外检测：如果'确定'图标仍然存在，说明可能卡在会员窗口未关闭，尝试再点一次确定
                    if image_on_screen('确定'):
                        print("检测到'确定'图标仍存在，尝试点击以推进...")
                        click_image('确定')
                    time.sleep(random.uniform(0.1, 0.3))
                if not vip_loaded:
                    print("超时：会员信息加载无响应，尝试通过点击'确定'和按ESC清理弹窗...")
                    # 尝试多种方式清理可能卡住的弹窗
                    for _ in range(3):
                        click_image('确定')
                        time.sleep(0.3)
                        pyautogui.press('esc')
                        time.sleep(0.3)
                    # 检测是否还有'确定'图标，如果有则说明弹窗还在
                    if image_on_screen('确定'):
                        print("弹窗未清理成功，放弃本次扫码")
                        return False
                    print("弹窗已清理，继续流程")
                    self.previous_vip = '超时'

            time.sleep(random.uniform(0.3, 0.6))

            pyautogui.keyDown('shift')
            pyautogui.press('=')
            pyautogui.keyUp('shift')
            time.sleep(random.uniform(0.3, 0.5))

            pyautogui.press(confirm_key)
            return True

        except Exception as e:
            print(f"扫码操作失败: {str(e)}")
            return False

    def revise_parameters(self):
        global wait_minutes, method2_probability, vip_probability
        self.input_texts['wait_min'] = str(wait_minutes[0])
        self.input_texts['wait_max'] = str(wait_minutes[1])
        self.input_texts['prob'] = str(int(method2_probability * 100))
        self.input_texts['vip_prob'] = str(int(vip_probability * 100))
        self.input_active = None
        active = True
        draw_needed = True
        mouse_pos_prev = None
        while active:
            for event in pygame.event.get():
                draw_needed = True
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = pygame.mouse.get_pos()
                    handled = False
                    for name, rect in self.input_boxes.items():
                        if rect.collidepoint(pos):
                            self.input_active = name
                            handled = True
                            break
                    if not handled:
                        self.input_active = None
                    for button in self.扫码间隔s:
                        if button[0].collidepoint(pos):
                            wait_minutes = (button[1][0], button[1][1])
                            self.input_texts['wait_min'] = str(wait_minutes[0])
                            self.input_texts['wait_max'] = str(wait_minutes[1])
                            break
                    for button in self.方法2概率s:
                        if button[0].collidepoint(pos):
                            method2_probability = button[1]
                            self.input_texts['prob'] = str(int(method2_probability * 100))
                            break
                    for button in self.VIP概率s:
                        if button[0].collidepoint(pos):
                            vip_probability = button[1]
                            self.input_texts['vip_prob'] = str(int(vip_probability * 100))
                            break
                    if self.done_button.collidepoint(pos):
                        try:
                            wm = int(self.input_texts['wait_min'])
                            wx = int(self.input_texts['wait_max'])
                            if 1 <= wm <= wx <= 1440:
                                wait_minutes = (wm, wx)
                        except ValueError:
                            pass
                        try:
                            p = int(self.input_texts['prob'])
                            if 0 <= p <= 100:
                                method2_probability = p / 100.0
                        except ValueError:
                            pass
                        try:
                            vp = int(self.input_texts['vip_prob'])
                            if 0 <= vp <= 100:
                                vip_probability = vp / 100.0
                        except ValueError:
                            pass
                        active = False
                        return
                if event.type == pygame.KEYDOWN and self.input_active:
                    txt = self.input_texts[self.input_active]
                    if event.key == pygame.K_BACKSPACE:
                        self.input_texts[self.input_active] = txt[:-1]
                    elif event.key == pygame.K_RETURN:
                        self.input_active = None
                    elif event.unicode.isdigit() and len(txt) < 4:
                        self.input_texts[self.input_active] = txt + event.unicode
            mouse_pos = pygame.mouse.get_pos()
            if mouse_pos != mouse_pos_prev:
                draw_needed = True
                mouse_pos_prev = mouse_pos
            if draw_needed:
                self.draw_revise_parameters()
                pygame.display.update()
                draw_needed = False
            clock.tick(15)

    def draw_revise_parameters(self):
        screen.fill(WHITE)
        screen.blit(Img.done, (self.done_button.x, self.done_button.y))

        # ===== 块1: 扫码间隔 (起始 y=20) =====
        # 标题 y=20, 预设行1 y=60, 预设行2 y=120, 自定义标签 y=175, 输入框 y=180
        text = font.render(f"扫码间隔：{wait_minutes[0]}~{wait_minutes[1]}分钟", True, BLACK)
        screen.blit(text, (100, 20))
        for i, button in enumerate(self.扫码间隔s):
            text = font.render(f"{button[1][0]}~{button[1][1]}分钟", True, BLACK)
            screen.blit(text, (button[0].x, button[0].y))

        text = font.render("自定义扫码间隔（分钟）：", True, BLACK)
        screen.blit(text, (100, 175))
        for name in ['wait_min', 'wait_max']:
            rect = self.input_boxes[name]
            color = LIGHT_BLUE if self.input_active == name else GRAY
            pygame.draw.rect(screen, color, rect, 2, border_radius=5)
            txt = self.input_texts[name]
            if self.input_active == name and int(time.time() * 2) % 2 == 0:
                txt += '|'
            t = font_small.render(txt, True, BLACK)
            screen.blit(t, (rect.x + 5, rect.y + 8))
        t = font_small.render("~", True, BLACK)
        screen.blit(t, (470, 190))

        # ===== 块2: 方法2概率 (起始 y=285) =====
        # 标题 y=285, 预设行 y=325, 自定义标签 y=390, 输入框 y=395
        text = font.render(f"方法2概率：{method2_probability*100:.0f}%", True, BLACK)
        screen.blit(text, (100, 285))
        for i, button in enumerate(self.方法2概率s):
            text = font.render(f"{button[1]*100:.0f}%", True, BLACK)
            screen.blit(text, (button[0].x, button[0].y))

        text = font.render("自定义方法2概率（%）：", True, BLACK)
        screen.blit(text, (100, 390))
        rect = self.input_boxes['prob']
        color = LIGHT_BLUE if self.input_active == 'prob' else GRAY
        pygame.draw.rect(screen, color, rect, 2, border_radius=5)
        txt = self.input_texts['prob']
        if self.input_active == 'prob' and int(time.time() * 2) % 2 == 0:
            txt += '|'
        t = font_small.render(txt, True, BLACK)
        screen.blit(t, (rect.x + 5, rect.y + 8))

        # ===== 块3: VIP概率 (起始 y=490) =====
        # 标题 y=490, 预设行 y=530, 自定义标签 y=595, 输入框 y=600
        text = font.render(f"VIP概率：{vip_probability*100:.0f}%", True, BLACK)
        screen.blit(text, (100, 490))
        for i, button in enumerate(self.VIP概率s):
            text = font.render(f"{button[1]*100:.0f}%", True, BLACK)
            screen.blit(text, (button[0].x, button[0].y))

        text = font.render("自定义VIP概率（%）：", True, BLACK)
        screen.blit(text, (100, 595))
        rect = self.input_boxes['vip_prob']
        color = LIGHT_BLUE if self.input_active == 'vip_prob' else GRAY
        pygame.draw.rect(screen, color, rect, 2, border_radius=5)
        txt = self.input_texts['vip_prob']
        if self.input_active == 'vip_prob' and int(time.time() * 2) % 2 == 0:
            txt += '|'
        t = font_small.render(txt, True, BLACK)
        screen.blit(t, (rect.x + 5, rect.y + 8))

        pos = pygame.mouse.get_pos()
        highlight(self.done_button, pos)
        for [button, value] in (self.方法2概率s + self.扫码间隔s + self.VIP概率s):
            highlight(button, pos)

    def view_records(self):
        active = True
        self.record_scroll = 0
        self.record_tab = 0
        draw_needed = True
        while active:
            for event in pygame.event.get():
                draw_needed = True
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        pos = event.pos
                        tab1 = pygame.Rect(100, 50, 200, 40)
                        tab2 = pygame.Rect(350, 50, 200, 40)
                        back_btn = pygame.Rect(1150, 600, 100, 50)
                        if tab1.collidepoint(pos):
                            self.record_tab = 0
                            self.record_scroll = 0
                        elif tab2.collidepoint(pos):
                            self.record_tab = 1
                            self.record_scroll = 0
                        elif back_btn.collidepoint(pos):
                            active = False
                            return
                    elif event.button == 4:
                        self.record_scroll = max(0, self.record_scroll - 30)
                    elif event.button == 5:
                        self.record_scroll += 30
            if draw_needed:
                self.draw_records_view()
                pygame.display.update()
                draw_needed = False
            clock.tick(15)

    def draw_records_view(self):
        screen.fill(WHITE)

        tab1 = pygame.Rect(100, 50, 200, 40)
        tab2 = pygame.Rect(350, 50, 200, 40)

        c1 = LIGHT_BLUE if self.record_tab == 0 else GRAY
        c2 = LIGHT_BLUE if self.record_tab == 1 else GRAY
        pygame.draw.rect(screen, c1, tab1, border_radius=5)
        pygame.draw.rect(screen, c2, tab2, border_radius=5)

        t1 = font.render("扫码记录", True, BLACK)
        t2 = font.render("本月未扫", True, BLACK)
        screen.blit(t1, (tab1.x + 50, tab1.y + 8))
        screen.blit(t2, (tab2.x + 50, tab2.y + 8))

        back_btn = pygame.Rect(1150, 600, 100, 50)
        screen.blit(Img.quit, (back_btn.x, back_btn.y))
        pos = pygame.mouse.get_pos()
        highlight(back_btn, pos)
        highlight(tab1, pos)
        highlight(tab2, pos)

        clip_rect = pygame.Rect(50, 100, window_width - 100, window_height - 170)
        screen.set_clip(clip_rect)

        if self.record_tab == 0:
            records = _load_vip_records()
            records_reversed = list(reversed(records))
            line_h = 30
            max_scroll = max(0, len(records_reversed) * line_h - clip_rect.height)
            self.record_scroll = min(self.record_scroll, max_scroll)

            header = font_small.render(f"{'序号':<6}{'会员编号':<15}{'扫码时间'}", True, BLUE)
            screen.blit(header, (100, 110 - self.record_scroll))
            pygame.draw.line(screen, GRAY, (100, 132 - self.record_scroll), (window_width - 100, 132 - self.record_scroll))

            for i, r in enumerate(records_reversed):
                y = 140 + i * line_h - self.record_scroll
                if y < 90 or y > window_height - 80:
                    continue
                idx = len(records) - i
                line = f"{idx:<6}{r['vip']:<15}{r['time']}"
                text = font_small.render(line, True, BLACK)
                screen.blit(text, (100, y))
        else:
            unscanned = _get_unscanned_this_month()
            line_h = 30
            max_scroll = max(0, len(unscanned) * line_h - clip_rect.height)
            self.record_scroll = min(self.record_scroll, max_scroll)

            now = datetime.datetime.now()
            header = font_small.render(f"本月({now.strftime('%Y-%m')}) 未扫会员  共 {len(unscanned)} 人", True, BLUE)
            screen.blit(header, (100, 110 - self.record_scroll))
            pygame.draw.line(screen, GRAY, (100, 132 - self.record_scroll), (window_width - 100, 132 - self.record_scroll))

            col_width = 200
            cols = max(1, (window_width - 200) // col_width)
            rows_per_col = max(1, (len(unscanned) + cols - 1) // cols)

            for i, v in enumerate(unscanned):
                col = i // rows_per_col
                row = i % rows_per_col
                x = 100 + col * col_width
                y = 140 + row * line_h - self.record_scroll
                if y < 90 or y > window_height - 80:
                    continue
                text = font_small.render(f"{i+1}. {v}", True, BLACK)
                screen.blit(text, (x, y))

        screen.set_clip(None)

    def draw(self):
        screen.fill(WHITE)

        y = 100
        text = font.render(f"扫码间隔：{wait_minutes[0]}~{wait_minutes[1]}分钟", True, BLACK)
        screen.blit(text, (100, y)); y += 25
        text = font.render(f"方法2概率：{method2_probability*100:.0f}%", True, BLACK)
        screen.blit(text, (100, y)); y += 25
        text = font.render(f"vip概率：{vip_probability*100:.0f}%", True, BLACK)
        screen.blit(text, (100, y)); y += 30
        m, s = divmod(self.wait_time, 60)
        text = font.render(f"剩余需等待时间：{int(m)}分{int(s)}秒", True, BLACK)
        screen.blit(text, (100, y)); y += 25
        text = font.render(f"下次扫码时间：{self.next_time.strftime('%H:%M:%S')}", True, BLACK)
        screen.blit(text, (100, y)); y += 25
        text = font.render(f"上次扫码条码：{self.previous_barcode}", True, BLACK)
        screen.blit(text, (100, y)); y += 25
        text = font.render(f"上次扫码vip：{self.previous_vip}", True, BLACK)
        screen.blit(text, (100, y)); y += 25
        text = font.render(f"上次扫码方式：{self.previous_method}", True, BLACK)
        screen.blit(text, (100, y))

        text = font.render(f"全局快捷键：Alt+X 立即扫码", True, BLUE)
        screen.blit(text, (800, 100))

        unscanned = _get_unscanned_this_month()
        records = _load_vip_records()
        now = datetime.datetime.now()
        month_prefix = now.strftime('%Y-%m')
        month_count = sum(1 for r in records if r['time'].startswith(month_prefix))
        text = font.render(f"本月已扫：{month_count}人", True, BLACK)
        screen.blit(text, (800, 135))
        text = font.render(f"本月未扫：{len(unscanned)}人", True, BLACK)
        screen.blit(text, (800, 160))

        screen.blit(Img.revise, (self.revise_button.x, self.revise_button.y))
        screen.blit(Img.immediately, (self.immediately_button.x, self.immediately_button.y))
        screen.blit(Img.reset_time, (self.reset_time_button.x, self.reset_time_button.y))
        screen.blit(Img.quit, (self.quit_button.x, self.quit_button.y))
        screen.blit(Img.save_vip, (self.record_button.x, self.record_button.y))
        
        pos = pygame.mouse.get_pos()
        highlight(self.revise_button, pos)
        highlight(self.quit_button, pos)
        highlight(self.immediately_button, pos)
        highlight(self.reset_time_button, pos)
        highlight(self.record_button, pos)

        

    def run(self):
        print("程序核心逻辑加载完成，启动主界面...")
        active = True
        last_update = time.time()
        draw_needed = True
        mouse_pos_prev = None

        while active:
            current_time = time.time()
            elapsed = current_time - last_update

            if elapsed >= 1:
                with self.lock:
                    self.wait_time -= 1
                last_update = current_time
                draw_needed = True

            for event in pygame.event.get():
                draw_needed = True
                if event.type == pygame.QUIT:
                    self.key_listener.stop()
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = pygame.mouse.get_pos()
                    if self.revise_button.collidepoint(pos):
                        print("修改参数")
                        self.revise_parameters()
                        break
                    elif self.quit_button.collidepoint(pos):
                        print("退出程序")
                        self.key_listener.stop()
                        sys.exit()
                    elif self.immediately_button.collidepoint(pos):
                        print("立即扫码（按钮）")
                        with self.lock:
                            if not self.scan_the_barcode():
                                print("扫码失败，等待下一次扫码")
                            self.wait_time, self.next_time = self.get_wait_time_and_next_time()
                    elif self.reset_time_button.collidepoint(pos):
                        print("重置扫码间隔")
                        with self.lock:
                            self.wait_time, self.next_time = self.get_wait_time_and_next_time()
                    elif self.record_button.collidepoint(pos):
                        print("查看扫码记录")
                        self.view_records()

            mouse_pos = pygame.mouse.get_pos()
            if mouse_pos != mouse_pos_prev:
                draw_needed = True
                mouse_pos_prev = mouse_pos

            if draw_needed:
                self.draw()
                pygame.display.flip()
                draw_needed = False

            clock.tick(15)

            with self.lock:
                if self.wait_time <= 0:
                    print("扫码间隔时间已到，开始扫码")
                    if not self.scan_the_barcode():
                        print("扫码失败，等待下一次扫码")
                    self.wait_time, self.next_time = self.get_wait_time_and_next_time()

if __name__ == '__main__':
    print("=" * 50)
    print("POS扫码程序 - 启动中")
    print("第一步：检测管理员权限...")
    if not is_admin():
        run_as_admin()
    else:
        print("已获取管理员权限！")
        print("第二步：加载程序核心逻辑...")
        prinput("按Enter键继续启动程序（如需调试可在此暂停）...")
    try:
        scanner = Scanner()
        scanner.run()
    except KeyboardInterrupt:
        print("程序被手动终止")
        input("按Enter键退出...")
    finally:
        pygame.quit()
        sys.exit()
