import json
import os
import threading
import time
from json import JSONDecodeError
from queue import Queue
from threading import Thread

import requests


SAVE_CACHE_TIME_THRESHOLD = 120
REFRESH_CACHE_TIME_THRESHOLD = 180


def get_chain_price_info_api_call(chain_name):
    try:
        info = requests.get(
            url="https://chiafork.space/API/" + chain_name + ".json",
            params={},
            headers={}
        ).json()
    except ConnectionError:
        info = {}
    except JSONDecodeError:
        info = {}
    return info


class ChainPriceInfoInfoCache(object):

    def __init__(self):
        self.last_save_cache_time = 0
        self.chain_price_info_cache = {}
        self.cache_file_path_name = 'cache/chain_price_info_caches.json'
        if os.path.exists(self.cache_file_path_name):
            with open(self.cache_file_path_name, 'rb') as f:
                try:
                    self.chain_price_info_cache = json.loads(str(f.read(), encoding='utf-8'))
                except JSONDecodeError:
                    pass
        self.get_chain_price_info_msg_queue = Queue()
        self.msg_queue_is_not_empty = threading.Event()
        self.msg_queue_is_not_empty.clear()
        self.get_chain_price_info_thread = Thread(target=self.get_chain_price_info_thread_fun,
                                                  args=(self.get_chain_price_info_msg_queue,))

    def get_chain_price_info_thread_fun(self, msg_queue: Queue):
        stop = False
        while not stop:
            self.msg_queue_is_not_empty.wait(1)
            while not msg_queue.empty():
                msg = msg_queue.get()
                if msg == 'stop':
                    stop = True
                    break
                chain_name = msg['chain_name']
                info = get_chain_price_info_api_call(chain_name)
                self.chain_price_info_cache[chain_name] = {'timestamp': time.time(), 'info': info}
            if time.time() - self.last_save_cache_time >= SAVE_CACHE_TIME_THRESHOLD:
                self.save_cache()

    def save_cache(self):
        self.last_save_cache_time = time.time()
        with open(self.cache_file_path_name, 'wb+') as chain_price_info_caches_file:
            chain_price_info_caches_file.write(
                bytes(json.dumps(self.chain_price_info_cache), encoding='utf8')
            )

    def get_chain_price_info(self, chain):
        if chain.chain_name not in self.chain_price_info_cache:
            info = get_chain_price_info_api_call(chain.chain_name)
            self.chain_price_info_cache[chain.chain_name] = {'timestamp': time.time(), 'info': info}
            self.save_cache()
        else:
            info = self.chain_price_info_cache[chain.chain_name]['info']
            if time.time() - self.chain_price_info_cache[chain.chain_name]['timestamp'] > REFRESH_CACHE_TIME_THRESHOLD:
                self.get_chain_price_info_msg_queue.put({'chain_name': chain.chain_name})
                self.msg_queue_is_not_empty.set()
        return info

    def stop(self):
        self.get_chain_price_info_msg_queue.put('stop')
        self.msg_queue_is_not_empty.set()
