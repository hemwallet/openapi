import json
import os
import threading
import time
from json import JSONDecodeError
from queue import Queue
from threading import Thread

import requests


SAVE_CACHE_TIME_THRESHOLD = 180
REFRESH_CACHE_TIME_THRESHOLD = 120


def get_tail_info_api_call(tail_puzzlehash, chain_id):
    try:
        if chain_id == '0x01':
            info = requests.get(
                url="https://api.taildatabase.com/enterprise/tail/" + tail_puzzlehash,
                params={},
                headers={"accept": "application/json", "x-api-version": "2"}
            ).json()
        else:
            info = {}
    except ConnectionError:
        info = {}
    except JSONDecodeError:
        info = {}
    return info


class TailInfoCache(object):

    def __init__(self):
        self.last_save_cache_time = 0
        self.tail_info_caches = {}
        self.cache_file_path_name = 'cache/tail_info_caches.json'
        if os.path.exists(self.cache_file_path_name):
            with open(self.cache_file_path_name, 'rb') as f:
                try:
                    self.tail_info_caches = json.loads(str(f.read(), encoding='utf-8'))
                except JSONDecodeError:
                    pass
        self.get_tail_info_msg_queue = Queue()
        self.msg_queue_is_not_empty = threading.Event()
        self.msg_queue_is_not_empty.clear()
        self.get_tail_info_thread = Thread(target=self.get_tail_info_thread_fun, args=(self.get_tail_info_msg_queue,))

    def get_tail_info_thread_fun(self, msg_queue: Queue):
        stop = False
        while not stop:
            self.msg_queue_is_not_empty.wait(1)
            presented_tail_puzzlehash = []
            while not msg_queue.empty():
                msg = msg_queue.get()
                if msg == 'stop':
                    stop = True
                    break
                tail_puzzlehash = msg['tail_puzzlehash']
                if tail_puzzlehash not in presented_tail_puzzlehash:
                    presented_tail_puzzlehash.append(tail_puzzlehash)
                    chain_id = msg['chain_id']
                    info = get_tail_info_api_call(tail_puzzlehash, chain_id)
                    self.tail_info_caches[chain_id][tail_puzzlehash] = {'timestamp': time.time(), 'info': info}
            presented_tail_puzzlehash.clear()
            if time.time() - self.last_save_cache_time >= SAVE_CACHE_TIME_THRESHOLD:
                self.save_cache()

    def save_cache(self):
        self.last_save_cache_time = time.time()
        with open(self.cache_file_path_name, 'wb+') as tail_info_caches_file:
            tail_info_caches_file.write(bytes(json.dumps(self.tail_info_caches), encoding='utf8'))

    def get_tail_info(self, chain, tail_puzzlehash: str):
        if chain.id not in self.tail_info_caches:
            self.tail_info_caches[chain.id] = {}
        tail_info_cache = self.tail_info_caches[chain.id]
        if tail_puzzlehash not in tail_info_cache:
            info = get_tail_info_api_call(tail_puzzlehash, chain.id)
            tail_info_cache[tail_puzzlehash] = {'timestamp': time.time(), 'info': info}
            self.save_cache()
        else:
            info = tail_info_cache[tail_puzzlehash]['info']
            if time.time() - tail_info_cache[tail_puzzlehash]['timestamp'] > REFRESH_CACHE_TIME_THRESHOLD:
                self.get_tail_info_msg_queue.put({'tail_puzzlehash': tail_puzzlehash, 'chain_id': chain.id})
                self.msg_queue_is_not_empty.set()
        return info

    def stop(self):
        self.get_tail_info_msg_queue.put('stop')
        self.msg_queue_is_not_empty.set()
