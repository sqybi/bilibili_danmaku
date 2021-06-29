import aiohttp
import asyncio
from datetime import datetime
import os
import random
import sys
import threading
import traceback
import uuid

from aip import AipSpeech
from playsound import playsound
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem
import ujson

from . import Ui_danmaku_app, bilibili


CONFIG_FILE_NAME = 'config.json'

ws = None
ws_cond = None
ui = None
ui_cond = threading.Condition()
ui_prepared = False
config = {}

# Baidu AIP TTS
TTS_CLIENT = None


async def init_ws():
    global ws

    retry = 0
    while retry != -1:
        status_text = '⌛正在连接弹幕服务器……'
        if retry != 0:
            status_text += f'\n（第{retry}次重试）'
        ui.label_status.setText(status_text)
        try:
            session = aiohttp.ClientSession()
            ws_url, reg_datas = await bilibili.Bilibili.get_ws_info(
                'https://live.bilibili.com/{}'.format(ui.lineEdit_room_number.text()))
            ws = await session.ws_connect(ws_url)
            for reg_data in reg_datas:
                await ws.send_bytes(reg_data)
            retry = -1
        except:
            await asyncio.sleep(1)
            retry += 1

    ui.label_status.setText('✔️已经连接到弹幕服务器！')


async def init_tts():
    global TTS_CLIENT
    TTS_CLIENT = AipSpeech(ui.lineEdit_app_id.text(), ui.lineEdit_api_key.text(), ui.lineEdit_secret_key.text())


async def heartbeats():
    while True:
        async with ws_cond:
            if ws is None or ws.closed:
                await init_ws()
                ws_cond.notify_all()
        await asyncio.sleep(bilibili.Bilibili.heartbeatInterval)
        if bilibili.Bilibili.heartbeat:
            try:
                await ws.send_bytes(bilibili.Bilibili.heartbeat)
            except:
                pass


async def fetch_danmaku(dm_queue):
    while True:
        async with ws_cond:
            while ws is None or ws.closed:
                await ws_cond.wait()
            async for msg in ws:
                ms = bilibili.Bilibili.decode_msg(msg.data)
                for m in ms:
                    if dm_queue.full():
                        await dm_queue.get()
                    await dm_queue.put(m)
        await asyncio.sleep(1)


async def process_danmaku_queue(dm_queue):
    while True:
        m = await dm_queue.get()
        with open('data.log', 'w+') as f:
            f.write('{}\n{}\n\n'.format(datetime.today().strftime('%Y-%m-%d %H:%M:%S'), m))
        if m['msg_type'] == 'danmaku':
            await process_danmaku(m)


async def process_danmaku(data):
    try:
        user = data['name']
        msg = data['content']
        audio_text = f'{user}说：{msg}'

        # Commands
        if msg == '念诗':
            poem = await get_random_poem()
            audio_text = f'{user}触发的随机念诗：{poem}'

        # Set UI
        rowIndex = ui.tableWidget.rowCount()
        ui.tableWidget.setRowCount(rowIndex + 1)
        ui.tableWidget.setItem(rowIndex, 0, QTableWidgetItem(str(datetime.today().strftime('%Y-%m-%d %H:%M:%S'))))
        ui.tableWidget.setItem(rowIndex, 1, QTableWidgetItem(user))
        ui.tableWidget.setItem(rowIndex, 2, QTableWidgetItem(msg))
        ui.tableWidget.setItem(rowIndex, 3, QTableWidgetItem(audio_text))

        count = 0
        while True:
            try:
                result = TTS_CLIENT.synthesis(
                    audio_text,
                    'zh',
                    1,
                    {
                        'spd': ui.spinBox_spd.value(),
                        'pit': ui.spinBox_pit.value(),
                        'vol': ui.spinBox_vol.value(),
                        'per': ui.comboBox_per.currentIndex()
                    }
                )
                if not isinstance(result, dict):
                    fn = str(uuid.uuid4()) + '.mp3'
                    with open(fn, 'wb') as f:
                        f.write(result)
                    playsound(fn)
                    os.remove(fn)
            except:
                count += 1
                if count <= 3:
                    continue
                else:
                    raise
            break
    except:
        traceback.print_exc()
        for colIndex in range(ui.tableWidget.columnCount()):
            ui.tableWidget.item(rowIndex, colIndex).setBackground(QBrush(Qt.GlobalColor.red))


async def get_random_poem():
    data = [
        '人是衣马是鞍 一看长相二看穿',
        '白天想 夜里哭 做梦都想去首都',
        '俩脚离地了 病毒就关闭了 啥都上不去了 嗷',
        '改革春风吹满地 吹满地 春风吹满地',
        '中国人民真争气 真争气 人民真争气',
        '这个世界太疯狂 耗子都给猫当伴娘',
        '齐德隆 齐东强 齐德隆的咚得隆咚锵',
        '记得那是2003年的第一场雪 第一场雪',
        '比2002年来滴稍晚了一些 稍晚了一些',
        '抓牌 看牌 洗牌 马牌',
        '失败 知道因为啥失败吗 真让我替你感到悲哀',
        '不打针 不吃药 坐着就是跟你唠',
        '用谈话的方式治疗这叫话疗',
        '现在请听第一个话题 母猪的产后护理 拿错书了',
        '粮食大丰收 洪水被赶跑',
        '百姓安居乐业 齐夸党的领导',
        '国外比较乱遭 整天勾心斗角',
        '纵观世界风云 风景这边更好',
        '火辣辣的心呐 火辣辣的情',
        '火辣辣的小辣椒他透着心里红',
        '火辣辣的范老师请你多批评',
        '精辟啥 那是屁精',
        '我在意你 含糊你 伺候你',
        '我不光怕你 关键现在我怕你妈呀',
        '喝水 闭嘴 揉腿 亲一口老鬼',
        '感谢TV 感谢所有TV',
        '床前明月光 玻璃玻璃好上霜',
        '打麻将 双人床 十个木那叫念炕',
        '一只公鸡要下蛋 不是它的活它要干',
    ]
    return random.choice(data)


async def start_watcher_main():
    global ws_cond
    ws_cond = asyncio.Condition()
    dm_queue = asyncio.Queue(maxsize=ui.spinBox_queue_size.value())
    await asyncio.gather(init_tts(), heartbeats(), fetch_danmaku(dm_queue), process_danmaku_queue(dm_queue))


def start_watcher_task(loop):
    with ui_cond:
        while not ui_prepared:
            ui_cond.wait()
    asyncio.set_event_loop(loop)
    future = asyncio.run(start_watcher_main())
    loop.run_until_complete(future)


## App

def event_start_watcher():
    global ui_prepared
    ui.lineEdit_room_number.setEnabled(False)
    ui.spinBox_queue_size.setEnabled(False)
    ui.lineEdit_app_id.setEnabled(False)
    ui.lineEdit_api_key.setEnabled(False)
    ui.lineEdit_secret_key.setEnabled(False)
    ui.pushButton.setEnabled(False)
    with ui_cond:
        ui_prepared = True
        ui_cond.notify_all()
    ui.pushButton.setText('正在接收弹幕中！')


def event_room_number_text_changed():
    config['room_number'] = ui.lineEdit_room_number.text()
    save_config()


def event_queue_size_value_changed():
    config['queue_size'] = ui.spinBox_queue_size.value()
    save_config()


def event_app_id_text_changed():
    config['app_id'] = ui.lineEdit_app_id.text()
    save_config()


def event_api_key_text_changed():
    config['api_key'] = ui.lineEdit_api_key.text()
    save_config()


def event_secret_key_text_changed():
    config['secret_key'] = ui.lineEdit_secret_key.text()
    save_config()


def event_spd_value_changed():
    config['spd'] = ui.spinBox_spd.value()
    save_config()


def event_pit_value_changed():
    config['pit'] = ui.spinBox_pit.value()
    save_config()


def event_vol_value_changed():
    config['vol'] = ui.spinBox_vol.value()
    save_config()


def event_per_index_changed():
    config['per'] = ui.comboBox_per.currentIndex()
    save_config()


def save_config():
    with open(CONFIG_FILE_NAME, 'w') as f:
        ujson.dump(config, f)


def set_text_by_config(obj, key):
    if key in config:
        obj.setText(config.get(key))


def set_value_by_config(obj, key):
    if key in config:
        obj.setValue(config.get(key))


def set_index_by_config(obj, key):
    if key in config:
        obj.setCurrentIndex(config.get(key))


def load_ui_data():
    global config
    if os.path.isfile(CONFIG_FILE_NAME):
        with open(CONFIG_FILE_NAME, 'r') as f:
            config = ujson.load(f)
    else:
        save_config()

    set_text_by_config(ui.lineEdit_room_number, 'room_number')
    set_value_by_config(ui.spinBox_queue_size, 'queue_size')
    set_text_by_config(ui.lineEdit_app_id, 'app_id')
    set_text_by_config(ui.lineEdit_api_key, 'api_key')
    set_text_by_config(ui.lineEdit_secret_key, 'secret_key')
    set_value_by_config(ui.spinBox_spd, 'spd')
    set_value_by_config(ui.spinBox_pit, 'pit')
    set_value_by_config(ui.spinBox_vol, 'vol')
    set_index_by_config(ui.comboBox_per, 'per')


def start_app():
    global ui
    app = QApplication(sys.argv)
    MainWindow = QMainWindow()
    ui = Ui_danmaku_app.Ui_MainWindow()
    ui.setupUi(MainWindow)
    ui.lineEdit_room_number.textChanged.connect(event_room_number_text_changed)
    ui.spinBox_queue_size.valueChanged.connect(event_queue_size_value_changed)
    ui.lineEdit_app_id.textChanged.connect(event_app_id_text_changed)
    ui.lineEdit_api_key.textChanged.connect(event_api_key_text_changed)
    ui.lineEdit_secret_key.textChanged.connect(event_secret_key_text_changed)
    ui.spinBox_spd.valueChanged.connect(event_spd_value_changed)
    ui.spinBox_pit.valueChanged.connect(event_pit_value_changed)
    ui.spinBox_vol.valueChanged.connect(event_vol_value_changed)
    ui.comboBox_per.currentIndexChanged.connect(event_per_index_changed)
    ui.pushButton.clicked.connect(event_start_watcher)
    load_ui_data()
    MainWindow.show()
    app.exec_()


if __name__ == '__main__':
    thread_loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_watcher_task, args=(thread_loop,))
    t.daemon = True
    t.start()
    start_app()
