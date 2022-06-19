import json
import os
import threading
import time
from json import JSONDecodeError
from queue import Queue
from threading import Thread

import requests


SAVE_CACHE_TIME_THRESHOLD = 120
REFRESH_CACHE_TIME_THRESHOLD = 1800


def get_all_tail_list_info_api_call(chain_id):
    try:
        if chain_id == '0x01':
            info = requests.get(
                url="https://api.taildatabase.com/enterprise/tails/",
                params={},
                headers={"accept": "application/json", "x-api-version": "2"}
            ).json()
        else:
            return []
    except ConnectionError:
        info = []
    except JSONDecodeError:
        info = []
    return info


class AllTailListInfoCache(object):

    def __init__(self):
        self.last_save_cache_time = 0
        self.all_tail_list_info_cache = {}
        self.cache_file_path_name = 'cache/all_tail_list_info_caches.json'
        if os.path.exists(self.cache_file_path_name):
            with open(self.cache_file_path_name, 'rb') as f:
                try:
                    self.all_tail_list_info_cache = json.loads(str(f.read(), encoding='utf-8'))
                except JSONDecodeError:
                    pass
        self.get_all_tail_list_info_msg_queue = Queue()
        self.msg_queue_is_not_empty = threading.Event()
        self.msg_queue_is_not_empty.clear()
        self.get_all_tail_list_info_thread = Thread(target=self.get_all_tail_list_info_thread_fun,
                                                    args=(self.get_all_tail_list_info_msg_queue,))

    def get_all_tail_list_info_thread_fun(self, msg_queue: Queue):
        stop = False
        while not stop:
            self.msg_queue_is_not_empty.wait(1)
            while not msg_queue.empty():
                msg = msg_queue.get()
                if msg == 'stop':
                    stop = True
                    break
                chain_id = msg['chain_id']
                info = get_all_tail_list_info_api_call(chain_id)
                self.all_tail_list_info_cache[chain_id] = {'timestamp': time.time(), 'info': info}
            if time.time() - self.last_save_cache_time >= SAVE_CACHE_TIME_THRESHOLD:
                self.save_cache()

    def save_cache(self):
        self.last_save_cache_time = time.time()
        with open(self.cache_file_path_name, 'wb+') as all_tail_list_info_caches_file:
            all_tail_list_info_caches_file.write(
                bytes(json.dumps(self.all_tail_list_info_cache), encoding='utf8')
            )

    def get_all_tail_list_info(self, chain):
        if chain.id not in self.all_tail_list_info_cache:
            info = get_all_tail_list_info_api_call(chain.id)
            self.all_tail_list_info_cache[chain.id] = {'timestamp': time.time(), 'info': info}
            self.save_cache()
        else:
            info = self.all_tail_list_info_cache[chain.id]['info']
            if time.time() - self.all_tail_list_info_cache[chain.id]['timestamp'] > REFRESH_CACHE_TIME_THRESHOLD:
                self.get_all_tail_list_info_msg_queue.put({'chain_id': chain.id})
                self.msg_queue_is_not_empty.set()
        return info

    def stop(self):
        self.get_all_tail_list_info_msg_queue.put('stop')
        self.msg_queue_is_not_empty.set()
