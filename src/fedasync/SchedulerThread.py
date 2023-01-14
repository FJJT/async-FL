import copy
import threading
import time
from utils import ModuleFindTool
import random


class SchedulerThread(threading.Thread):
    def __init__(self, server_thread_lock, async_client_manager,
                 queue, current_t, scheduler_config,
                 server_network, t, idle_list, idle_list_thread_lock):
        threading.Thread.__init__(self)
        self.server_thread_lock = server_thread_lock
        self.schedule_interval = scheduler_config["scheduler_interval"]
        self.async_client_manager = async_client_manager
        self.queue = queue
        self.current_t = current_t
        self.server_network = server_network
        self.T = t
        schedule_class = ModuleFindTool.find_class_by_string("schedule", scheduler_config["schedule_file"], scheduler_config["schedule_name"])
        self.schedule = schedule_class()
        self.config = scheduler_config
        self.idle_list = idle_list
        self.idle_list_thread_lock = idle_list_thread_lock

    def run(self):
        last_s_time = -1
        # last_c_time = -1
        while self.current_t.get_time() < self.T:
            current_time = self.current_t.get_time()

            idle_len = 0
            self.idle_list_thread_lock.acquire()
            for i in self.idle_list:
                if i == True:
                    idle_len += 1
            self.idle_list_thread_lock.release()
            # 每隔一段时间进行一次schedule
            if current_time % self.schedule_interval == 0 and current_time != last_s_time and self.idleIsEnough(idle_len, self.config["params"]):
                print("| current_time |", current_time % self.schedule_interval, "= 0", current_time, "!=", last_s_time)
                print("| queue.size |", self.queue.qsize(), "<= 2 *", self.schedule_interval)
                # 如果server已收到且未使用的client更新数小于schedule interval，则进行schedule
                if self.queue.qsize() <= self.schedule_interval * 2:
                    last_s_time = current_time
                    print("Begin client select")
                    selected_client_threads = self.client_select(self.config["params"])
                    print("\nSchedulerThread select(", len(selected_client_threads), "clients):")
                    self.server_thread_lock.acquire()
                    server_weights = copy.deepcopy(self.server_network.state_dict())
                    self.server_thread_lock.release()
                    for s_client_thread in selected_client_threads:
                        print(s_client_thread.get_client_id(), end=" | ")
                        # 将server的模型参数和时间戳发给client
                        s_client_thread.set_client_weight(server_weights)
                        s_client_thread.set_time_stamp(current_time)
                        # 启动一次client线程
                        s_client_thread.set_event()
                    del server_weights
                    print("\n-----------------------------------------------------------------Schedule complete")
                else:
                    print("\n-----------------------------------------------------------------No Schedule")
                time.sleep(0.01)
            else:
                time.sleep(0.01)

    def client_select(self, params):
        client_list = self.async_client_manager.get_client_thread_list()
        select_num = int(params["c_ratio"] * len(client_list))

        if select_num < params["schedule_interval"] + 1:
            select_num = params["schedule_interval"] + 1
        idle_client_id = []
        self.idle_list_thread_lock.acquire()
        for i in range(len(self.idle_list)):
            if self.idle_list[i] == True:
                idle_client_id.append(i)
        self.idle_list_thread_lock.release()
        print("Current clients:", len(client_list), ", idle clients:", len(idle_client_id), ", select:", select_num)
        selected_client_id = random.sample(idle_client_id, select_num)

        selected_client_threads = []
        self.idle_list_thread_lock.acquire()
        for i in selected_client_id:
            self.idle_list[i] = False
            selected_client_threads.append(client_list[i])
        self.idle_list_thread_lock.release()
        return selected_client_threads
    def idleIsEnough(self, idle_len, params):
        if idle_len >= max(int(params["c_ratio"] * len(self.async_client_manager.get_client_thread_list())), params["schedule_interval"] + 1):
            return True
        else:
            return False



# import copy
# import threading
# import time
# from utils import ModuleFindTool
#
#
# class SchedulerThread(threading.Thread):
#     def __init__(self, server_thread_lock, async_client_manager,
#                  queue, current_t, scheduler_config,
#                  server_network, t):
#         threading.Thread.__init__(self)
#         self.server_thread_lock = server_thread_lock
#         self.schedule_interval = scheduler_config["scheduler_interval"]
#         self.async_client_manager = async_client_manager
#         self.queue = queue
#         self.current_t = current_t
#         self.server_network = server_network
#         self.T = t
#         schedule_class = ModuleFindTool.find_class_by_string("schedule", scheduler_config["schedule_file"], scheduler_config["schedule_name"])
#         self.schedule = schedule_class()
#         self.config = scheduler_config
#
#     def run(self):
#         last_s_time = -1
#         # last_c_time = -1
#         while self.current_t.get_time() <= self.T:
#             current_time = self.current_t.get_time() - 1
#             # 每隔一段时间进行一次schedule
#             if current_time % self.schedule_interval == 0 and current_time != last_s_time:
#                 print("| current_time |", current_time % self.schedule_interval, "= 0", current_time, "!=", last_s_time)
#                 print("| queue.size |", self.queue.qsize(), "<= 2 *", self.schedule_interval)
#                 # 如果server已收到且未使用的client更新数小于schedule interval，则进行schedule
#                 if self.queue.qsize() <= self.schedule_interval * 2:
#                     last_s_time = current_time
#                     print("Begin client select")
#                     selected_client_threads = self.client_select(self.config["params"])
#                     print("\nSchedulerThread select(", len(selected_client_threads), "clients):")
#                     self.server_thread_lock.acquire()
#                     server_weights = copy.deepcopy(self.server_network.state_dict())
#                     self.server_thread_lock.release()
#                     for s_client_thread in selected_client_threads:
#                         print(s_client_thread.get_client_id(), end=" | ")
#                         # 将server的模型参数和时间戳发给client
#                         s_client_thread.set_client_weight(server_weights)
#                         s_client_thread.set_time_stamp(current_time)
#                         # 启动一次client线程
#                         s_client_thread.set_event()
#                     del server_weights
#                     print("\n-----------------------------------------------------------------Schedule complete")
#                 else:
#                     print("\n-----------------------------------------------------------------No Schedule")
#                 time.sleep(0.01)
#             else:
#                 time.sleep(0.01)
#
#     def client_select(self, params):
#         client_list = self.async_client_manager.get_client_thread_list()
#         selected_client_threads = self.schedule.schedule(client_list, params)
#         return selected_client_threads
