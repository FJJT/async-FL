import threading

import torch.cuda
import time
from utils import ModuleFindTool


class AsyncClientManager:
    def __init__(self, init_weights, clients_num, multi_gpu, datasets, q, current_time, stop_event, client_config, manager_config,  idle_list, idle_list_thread_lock, queue_exist_event):
        self.init_weights = init_weights
        self.queue = q
        self.clients_num = clients_num
        self.batch_size = client_config["batch_size"]
        self.current_time = current_time
        self.stop_event = stop_event
        self.client_staleness_list = client_config["stale_list"]
        self.thread_lock = threading.Lock()
        self.epoch = client_config["epochs"]
        self.idle_list = idle_list
        self.idle_list_thread_lock = idle_list_thread_lock
        self.queue_exist_event = queue_exist_event
        self.test_filename = 'client_test_'+time.strftime("%Y_%m_%d+%H_%M", time.localtime(time.time()))+'.txt'
        self.test_filename_lock = threading.Lock()

        client_class = ModuleFindTool.find_class_by_string("client", manager_config["client_file"], manager_config["client_name"])

        # 初始化clients
        # 0: 多gpu，1：单gpu，2：cpu
        if torch.cuda.is_available():
            if multi_gpu:
                mode = 0
                dev_num = 0
                dev_total = torch.cuda.device_count()
            else:
                mode = 1
        else:
            mode = 2
        self.client_thread_list = []
        for i in range(clients_num):
            if mode == 0:
                dev = f'cuda:{dev_num}'
                dev_num = (dev_num + 1) % dev_total
            elif mode == 1:
                dev = 'cuda'
            else:
                dev = 'cpu'
            self.idle_list_thread_lock.acquire()
            self.idle_list[i] = True
            client_delay = self.client_staleness_list[i]
            dataset = datasets[i]
            self.client_thread_list.append(
                client_class(i, self.queue, self.stop_event, client_delay, dataset, client_config, dev,self.idle_list, self.idle_list_thread_lock, self.queue_exist_event, self.test_filename, self.test_filename_lock))
            self.idle_list_thread_lock.release()
        # 启动clients
        print("Start clients:")
        for client_thread in self.client_thread_list:
            client_thread.start()

    def stop_all_clients(self, server_weights, current_time):
        # 终止所有client线程
        test_string = "client_id" + '\t' + "round" + '\t' + "delay" + '\t' + "acc" + '\t' + "loss" + '\n'
        self.test_filename_lock.acquire()
        with open('./ex/' + self.test_filename, 'a') as file:
            file.write(test_string)
        self.test_filename_lock.release()
        self.stop_event.set()
        for client_threads in self.client_thread_list:
            # 将server的模型参数和时间戳发给client
            client_threads.set_client_weight(server_weights)
            client_threads.set_time_stamp(current_time)
            client_threads.set_event()

    def set_client_thread_list(self, new_client_thread_list):
        self.thread_lock.acquire()
        self.client_thread_list = new_client_thread_list
        self.thread_lock.release()

    def get_client_thread_list(self):
        self.thread_lock.acquire()
        client_thread_list = self.client_thread_list
        self.thread_lock.release()
        return client_thread_list

    def find_client_thread_by_c_id(self, c_id):
        self.thread_lock.acquire()
        target_client_thread = None
        for client_thread in self.client_thread_list:
            if client_thread.get_client_id() == c_id:
                target_client_thread = client_thread
        self.thread_lock.release()
        return target_client_thread
