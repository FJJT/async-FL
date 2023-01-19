import copy
import datetime
import os
import shutil
import threading
import sys
from utils.ConfigManager import *
from utils.Tools import *
from utils import ModuleFindTool, Queue, Time

if len(sys.argv) < 2:
    config_file = "config.json"
    # config_file = "config_fedavg.json"
else:
    config_file = sys.argv[1]

config = getConfig(config_file)
global_config = copy.deepcopy(config['global'])


# 数据集
dataset_class = ModuleFindTool.find_class_by_string("dataset", global_config["data_file"],
                                                    global_config["data_name"])
dataset = dataset_class(global_config["client_num"], global_config["iid"])
test_data = dataset.get_test_dataset()
train_data = dataset.get_train_dataset()
config['global']['iid'] = dataset.get_config()

#
# for i in range(len(train_data[0])):
#     print(train_data[0][i][1])
#     t = int(train_data[0][i][1])
#     print(t)
#     print(type(t))

for client in range(global_config["client_num"]):
    type_set = set()
    lable_list = [0 for k in range(10)]
    for i in range(len(train_data[client])):
        lable = 0
        lable_list[int(train_data[client][i][1])] += 1
        for temp_type in type_set:
            if(temp_type.equal(train_data[client][i][1])):
                lable = 1
        if lable == 0:
            type_set.add(train_data[client][i][1])
    print("clinet   ",client,"-----")
    print(lable_list)
    print(len(type_set))
    print(type_set)
    print(len(train_data[client]))
print(type(train_data))
print((type(train_data[0])))
print((type(train_data[0][0])))
print((type(train_data[0][0][1])))
#保存
torch.save(train_data, "non_iid_dataset.pth")
y = torch.load("non_iid_dataset.pth")
print(y[0][0][1])
print("---------------")
print(type(y))
print((type(y[0])))
print((type(y[0][0])))
print((type(y[0][0][1])))