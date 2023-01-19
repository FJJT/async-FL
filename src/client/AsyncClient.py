import copy
import time

from torch.utils.data import DataLoader

from client import Client
from utils import ModuleFindTool
import torch

class AsyncClient(Client.Client):
    def __init__(self, c_id, queue, stop_event, delay, train_ds, client_config, dev, idle_list, idle_list_thread_lock, queue_exist_event, test_filename, test_filename_lock):
        Client.Client.__init__(self, c_id, stop_event, delay, train_ds, dev)
        self.queue = queue
        self.batch_size = client_config["batch_size"]
        self.epoch = client_config["epochs"]
        self.model_name = client_config["model_name"]
        self.optimizer_config = client_config["optimizer"]
        self.mu = client_config["mu"]
        self.config = client_config
        self.idle_list = idle_list
        self.idle_list_thread_lock = idle_list_thread_lock
        self.queue_exist_event = queue_exist_event
        self.round = 0
        self.test_filename = test_filename
        self.test_filename_lock =test_filename_lock

        # 本地模型
        model_class = ModuleFindTool.find_class_by_string("model", client_config["model_file"], client_config["model_name"])
        self.model = model_class()
        self.model = self.model.to(self.dev)

        # 优化器
        opti_class = ModuleFindTool.find_opti_by_string(self.optimizer_config["name"])
        self.opti = opti_class(self.model.parameters(), lr=self.optimizer_config["lr"], weight_decay=self.optimizer_config["weight_decay"])

        self.test_data = train_ds
        # loss函数
        if isinstance(client_config["loss"], str):
            self.loss_func = ModuleFindTool.find_F_by_string(client_config["loss"])
        else:
            loss_func_class = ModuleFindTool.find_class_by_string("loss", client_config["loss"]["loss_file"], client_config["loss"]["loss_name"])
            self.loss_func = loss_func_class(client_config["loss"], self)
        self.train_dl = DataLoader(self.train_ds, batch_size=self.batch_size, shuffle=True)
    def run_server_test(self, epoch):
        dl = DataLoader(self.test_data, batch_size=100, shuffle=True)
        test_correct = 0
        test_loss = 0
        for data in dl:
            inputs, labels = data
            inputs, labels = inputs.to(self.dev), labels.to(self.dev)
            # outputs = self.server_network(inputs)
            outputs = self.model(inputs)
            _, id = torch.max(outputs.data, 1)
            test_loss += self.loss_func(outputs, labels).item()
            test_correct += torch.sum(id == labels.data).cpu().numpy()
        accuracy = test_correct / len(dl)
        loss = test_loss / len(dl)
        # self.loss_list.append(loss)
        # self.accuracy_list.append(accuracy)
        # print('Epoch(t):', epoch, 'accuracy:', accuracy, 'loss', loss)
        # if epoch == 0:
        #     with open('./ex/'+self.test_filename, 'w') as file:
        #         file.write("Epoch(t)\taccuracy\tloss\n")
        # test_string = str(epoch) + '\t' + str(accuracy) + '\t' + str(loss) + '\n'
        # with open('./ex/'+self.test_filename, 'a') as file:
        #     file.write(test_string)
        return accuracy, loss
    def run(self):
        while not self.stop_event.is_set():
            if self.received_weights:
                # 更新模型参数
                self.model.load_state_dict(self.weights_buffer, strict=True)
                self.received_weights = False
            if self.received_time_stamp:
                self.time_stamp = self.time_stamp_buffer
                self.received_time_stamp = False
            if self.event_is_set:
                self.event_is_set = False

            # 该client被选中，开始执行本地训练
            if self.event.is_set():
                self.round += 1
                self.client_thread_lock.acquire()
                # 该client进行训练
                r_weights = copy.deepcopy(self.model.state_dict())
                start_time = time.time()
                data_sum, weights = self.train_one_epoch(r_weights)
                end_time = time.time()
                true_train_time = end_time - start_time
                print("true_train_time___________________________",true_train_time)
                if self.delay - true_train_time > 0:
                    time.sleep(self.delay - true_train_time)
                else:
                    time.sleep(0)
                    print("\033[1;31m", "Client", self.client_id, "trained dalay smaller than true train time error", "\033[0m")
                # client传回server的信息具有延迟
                print("Client", self.client_id, "trained")


                # 返回其ID、模型参数和时间戳
                update_dict = {"client_id": self.client_id, "weights": weights, "data_sum": data_sum, "time_stamp": self.time_stamp}
                self.queue.put(update_dict)
                # 触发queue非空事件
                self.queue_exist_event.set()
                # 返回后，设置为空闲状态
                self.idle_list_thread_lock.acquire()
                self.idle_list[self.client_id] = True
                self.idle_list_thread_lock.release()
                self.event.clear()
                self.client_thread_lock.release()
            # 该client等待被选中
            else:
                self.event.wait()
        #退出循环中止进程
        #测试本地模型
        #加上if就是用本地数据测试全局模型，不加就是用本地数据测试本地模型
        if self.received_weights:
            # 更新模型参数
            self.model.load_state_dict(self.weights_buffer, strict=True)
            self.received_weights = False
        acc, loss = self.run_server_test(self.time_stamp_buffer)
        #记录训练数据
        test_string =str(self.client_id) + '\t' + str(self.round) + '\t' + str(self.delay) + '\t' + str(acc)\
                     + '\t' + str(loss) + '\n'
        self.test_filename_lock.acquire()

        with open('./ex/'+self.test_filename, 'a') as file:
            file.write(test_string)
        self.test_filename_lock.release()

    def train_one_epoch(self, r_weights):
        return self.model.train_one_epoch(self.epoch, self.dev, self.train_dl, self.model, self.loss_func, self.opti, self.mu)
