import aiohttp
import asyncio
from datetime import datetime
import os
import random
import uuid

from aip import AipSpeech
from playsound import playsound

from .bilibili import Bilibili


ROOM_ID = 22539
ws = None

# Baidu AIP TTS
TTS_APP_ID = '24434532'
TTS_API_KEY = 'csOwUbUbvragKtAa6ovWvVMj'
TTS_SECRET_KEY = 'jdGTPNG5cctxDEILr4Ij90C4z14v9nua'
TTS_CLIENT = AipSpeech(TTS_APP_ID, TTS_API_KEY, TTS_SECRET_KEY)

TTS_PARAM_SPEED = 9
TTS_PARAM_VOL = 7


async def init_ws():
    print('开始初始化……')
    global ws
    session = aiohttp.ClientSession()
    ws_url, reg_datas = await Bilibili.get_ws_info('https://live.bilibili.com/{}'.format(ROOM_ID))
    ws = await session.ws_connect(ws_url)
    for reg_data in reg_datas:
        await ws.send_bytes(reg_data)
    print('初始化连接完成！')


async def heartbeats():
    print('开始发送心跳……')
    while ws is not None and Bilibili.heartbeat:
        await asyncio.sleep(Bilibili.heartbeatInterval)
        try:
            await ws.send_bytes(Bilibili.heartbeat)
        except:
            pass


async def fetch_danmaku(dm_queue):
    print(f'开始抓取弹幕，房间号{ROOM_ID}……')
    while ws is not None:
        async for msg in ws:
            ms = Bilibili.decode_msg(msg.data)
            for m in ms:
                if dm_queue.full():
                    await dm_queue.get()
                await dm_queue.put(m)
        await asyncio.sleep(1)
        await init_ws()
        await asyncio.sleep(1)


async def process_danmaku_queue(dm_queue):
    print('开始处理弹幕……')
    print('----------')
    while ws is not None:
        m = await dm_queue.get()
        with open('data.log', 'w+') as f:
            f.write('{}\n{}\n\n'.format(datetime.today().strftime('%Y-%m-%d %H:%M:%S'), m))
        if m['msg_type'] == 'danmaku':
            await process_danmaku(m)


async def process_danmaku(data):
    try:
        user = data['name']
        msg = data['content']
        print(f'<{user}> {msg}')
        audio_text = f'{user}说：{msg}'

        # Commands
        if msg == '念诗':
            poem = await get_random_poem()
            audio_text = f'{user}触发的随机念诗：{poem}'
        print(audio_text)

        count = 0
        while True:
            try:
                result = TTS_CLIENT.synthesis(
                    audio_text,
                    'zh',
                    1,
                    {
                        'spd': TTS_PARAM_SPEED,
                        'vol': TTS_PARAM_VOL,
                    }
                )
                if isinstance(result, dict):
                    print(result)
                else:
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
        print('// 发生错误，读弹幕失败！')
    finally:
        print('----------')


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


async def main():
    dm_queue = asyncio.Queue(maxsize=10)
    await init_ws()
    await asyncio.gather(heartbeats(), fetch_danmaku(dm_queue), process_danmaku_queue(dm_queue))


if __name__ == '__main__':
    asyncio.run(main())
