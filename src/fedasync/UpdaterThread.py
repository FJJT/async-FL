import threading
import time

import torch.utils.data
#import wandb
from torch.utils.data import DataLoader
from utils import ModuleFindTool
import torch.nn.functional as F


class UpdaterThread(threading.Thread):
    def __init__(self, queue, server_thread_lock, t, current_t, server_network,
                 async_client_manager, stop_event, test_data, updater_config, idle_list, queue_exist_event):
        threading.Thread.__init__(self)
        self.queue = queue
        self.server_thread_lock = server_thread_lock
        self.T = t
        self.current_time = current_t
        self.server_network = server_network
        self.async_client_manager = async_client_manager
        self.stop_event = stop_event
        self.test_data = test_data

        self.queue_exist_event = queue_exist_event
        #self.queue_empty_event.clear()

        self.sum_delay = 0

        self.accuracy_list = []
        self.loss_list = []
        self.config = updater_config
        update_class = ModuleFindTool.find_class_by_string("update", updater_config["update_file"], updater_config["update_name"])
        self.update = update_class(self.config["params"])
        self.idle_list = idle_list

        self.test_filename = 'Epoch_test_'+time.strftime("%Y_%m_%d+%H_%M", time.localtime(time.time()))+'.txt'

        # loss函数
        if isinstance(updater_config["loss"], str):
            self.loss_func = ModuleFindTool.find_F_by_string(updater_config["loss"])
        else:
            self.loss_func = ModuleFindTool.find_class_by_string("loss", updater_config["loss"]["loss_file"], updater_config["loss"]["loss_name"])

    def run(self):
        for epoch in range(self.T):
            #循环待改进，参考client设计
            while True:
                c_r = 0
                # 接收一个client发回的模型参数和时间戳
                if not self.queue.empty():
                    # (c_id, client_weights, data_sum, time_stamp) = self.queue.get()
                    update_dict = self.queue.get()
                    c_id = update_dict["client_id"]
                    time_stamp = update_dict["time_stamp"]
                    self.sum_delay += (self.current_time.get_time() - time_stamp)
                    print("Updater received data from client", c_id, "| staleness =", time_stamp, "-",
                          self.current_time.get_time(), "| queue size = ", self.queue.qsize())

                    # 使用接收的client发回的模型参数和时间戳对全局模型进行更新
                    self.server_thread_lock.acquire()
                    self.update_server_weights(epoch, update_dict)
                    self.run_server_test(epoch)
                    self.server_thread_lock.release()
                    if self.queue.empty():
                        self.queue_exist_event.clear()
                    time.sleep(0.01)
                    break
                else:
                    time.sleep(0.01)
                    #? wait event ?
                    self.queue_exist_event.wait()

            self.current_time.time_add()
            print(self.current_time.get_time())
            time.sleep(0.01)

        print("Average delay =", (self.sum_delay / self.T))

        # 终止所有client线程
        self.async_client_manager.stop_all_clients(self.server_network.state_dict(), self.current_time.get_time())

    def update_server_weights(self, epoch, update_dict):
        updated_parameters = self.update.update_server_weights(self, epoch, update_dict)
        for key, var in updated_parameters.items():
            if torch.cuda.is_available():
                updated_parameters[key] = updated_parameters[key].cuda()
        self.server_network.load_state_dict(updated_parameters)

    def run_server_test(self, epoch):
        dl = DataLoader(self.test_data, batch_size=100, shuffle=True)
        test_correct = 0
        test_loss = 0
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        for data in dl:
            inputs, labels = data
            inputs, labels = inputs.to(dev), labels.to(dev)
            outputs = self.server_network(inputs)
            _, id = torch.max(outputs.data, 1)
            test_loss += self.loss_func(outputs, labels).item()
            test_correct += torch.sum(id == labels.data).cpu().numpy()
        accuracy = test_correct / len(dl)
        loss = test_loss / len(dl)
        self.loss_list.append(loss)
        self.accuracy_list.append(accuracy)
        print('Epoch(t):', epoch, 'accuracy:', accuracy, 'loss', loss)

        if epoch == 0:
            with open('./ex/'+self.test_filename, 'w') as file:
                file.write("Epoch(t)\taccuracy\tloss\n")
        test_string = str(epoch) + '\t' + str(accuracy) + '\t' + str(loss) + '\n'
        with open('./ex/'+self.test_filename, 'a') as file:
            file.write(test_string)

        return accuracy, loss

    def get_accuracy_and_loss_list(self):
        return self.accuracy_list, self.loss_list


# import threading
# import time
#
# import torch.utils.data
# #import wandb
# from torch.utils.data import DataLoader
# from utils import ModuleFindTool
# import torch.nn.functional as F
#
#
# class UpdaterThread(threading.Thread):
#     def __init__(self, queue, server_thread_lock, t, current_t, server_network,
#                  async_client_manager, stop_event, test_data, updater_config):
#         threading.Thread.__init__(self)
#         self.queue = queue
#         self.server_thread_lock = server_thread_lock
#         self.T = t
#         self.current_time = current_t
#         self.server_network = server_network
#         self.async_client_manager = async_client_manager
#         self.stop_event = stop_event
#         self.test_data = test_data
#
#         self.event = threading.Event()
#         self.event.clear()
#
#         self.sum_delay = 0
#
#         self.accuracy_list = []
#         self.loss_list = []
#         self.config = updater_config
#         update_class = ModuleFindTool.find_class_by_string("update", updater_config["update_file"], updater_config["update_name"])
#         self.update = update_class(self.config["params"])
#
#         # loss函数
#         if isinstance(updater_config["loss"], str):
#             self.loss_func = ModuleFindTool.find_F_by_string(updater_config["loss"])
#         else:
#             self.loss_func = ModuleFindTool.find_class_by_string("loss", updater_config["loss"]["loss_file"], updater_config["loss"]["loss_name"])
#
#     def run(self):
#         for epoch in range(self.T):
#             while True:
#                 c_r = 0
#                 # 接收一个client发回的模型参数和时间戳
#                 if not self.queue.empty():
#                     # (c_id, client_weights, data_sum, time_stamp) = self.queue.get()
#                     update_dict = self.queue.get()
#                     c_id = update_dict["client_id"]
#                     time_stamp = update_dict["time_stamp"]
#                     self.sum_delay += (self.current_time.get_time() - time_stamp)
#                     print("Updater received data from client", c_id, "| staleness =", time_stamp, "-",
#                           self.current_time.get_time(), "| queue size = ", self.queue.qsize())
#                     self.event.set()
#                 else:
#                     update_dict = {}
#
#                 if self.event.is_set():
#                     # 使用接收的client发回的模型参数和时间戳对全局模型进行更新
#                     self.server_thread_lock.acquire()
#                     self.update_server_weights(epoch, update_dict)
#                     self.run_server_test(epoch)
#                     self.server_thread_lock.release()
#                     self.event.clear()
#                     time.sleep(0.01)
#                     break
#                 else:
#                     time.sleep(0.01)
#
#             self.current_time.time_add()
#             time.sleep(0.01)
#
#         print("Average delay =", (self.sum_delay / self.T))
#
#         # 终止所有client线程
#         self.async_client_manager.stop_all_clients()
#
#     def update_server_weights(self, epoch, update_dict):
#         updated_parameters = self.update.update_server_weights(self, epoch, update_dict)
#         for key, var in updated_parameters.items():
#             if torch.cuda.is_available():
#                 updated_parameters[key] = updated_parameters[key].cuda()
#         self.server_network.load_state_dict(updated_parameters)
#
#     def run_server_test(self, epoch):
#         dl = DataLoader(self.test_data, batch_size=100, shuffle=True)
#         test_correct = 0
#         test_loss = 0
#         dev = 'cuda' if torch.cuda.is_available() else 'cpu'
#         for data in dl:
#             inputs, labels = data
#             inputs, labels = inputs.to(dev), labels.to(dev)
#             outputs = self.server_network(inputs)
#             _, id = torch.max(outputs.data, 1)
#             test_loss += self.loss_func(outputs, labels).item()
#             test_correct += torch.sum(id == labels.data).cpu().numpy()
#         accuracy = test_correct / len(dl)
#         loss = test_loss / len(dl)
#         self.loss_list.append(loss)
#         self.accuracy_list.append(accuracy)
#         print('Epoch(t):', epoch, 'accuracy:', accuracy, 'loss', loss)
#         # if self.config['enabled']:
#         #     wandb.log({'accuracy': accuracy, 'loss': loss})
#         return accuracy, loss
#
#     def get_accuracy_and_loss_list(self):
#         return self.accuracy_list, self.loss_list
