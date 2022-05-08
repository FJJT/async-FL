import copy

import torch
import torchvision
from torch.autograd import Variable
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
import numpy as np
from torch.utils.data import TensorDataset
from utils.Tools import *
from matplotlib import pyplot as plt
from torchvision.transforms import ToPILImage


class MNIST:
    def __init__(self, clients, is_iid=False):
        # 获取数据集
        train_datasets = datasets.MNIST(root='../data/', train=True,
                                        transform=transforms.ToTensor(), download=True)
        test_datasets = datasets.MNIST(root='../data/', train=False,
                                       transform=transforms.ToTensor(), download=True)
        train_data = train_datasets.data
        self.raw_data = train_datasets.data
        self.train_labels = train_datasets.targets
        test_data = test_datasets.data
        self.test_datasets = test_datasets
        # 归一化
        train_data = train_data.reshape(train_data.shape[0], train_data.shape[1] * train_data.shape[2])
        test_data = test_data.reshape(test_data.shape[0], test_data.shape[1] * test_data.shape[2])
        train_data = train_data.float()
        self.train_data = np.multiply(train_data, 1.0 / 255.0)  # 数组对应元素位置相乘
        test_data = test_data.float()
        self.test_data = np.multiply(test_data, 1.0 / 255.0)

        self.train_data_size = train_data.shape[0]
        self.datasets = []

        if is_iid:
            order = np.arange(self.train_data_size)
            np.random.shuffle(order)
            self.train_data = self.train_data[order]
            self.train_labels = self.train_labels[order]
        else:
            # order = np.argsort(self.train_labels)
            # saveOrder("IID/MNIST/order.txt", list(order))
            order = get_order_as_tuple("../results/IID/MNIST/order.txt")
            self.train_data = self.train_data[order]
            self.raw_data = self.raw_data[order]
            self.train_labels = self.train_labels[order]

        shard_size = self.train_data_size // clients // 2
        for i in range(clients):
            client_data1 = self.train_data[shard_size * i: shard_size * (i + 1)]
            client_data2 = self.train_data[shard_size * clients + shard_size * i: shard_size * clients + shard_size * (i + 1)]
            client_label1 = self.train_labels[shard_size * i: shard_size * (i + 1)]
            client_label2 = self.train_labels[shard_size * clients + shard_size * i: shard_size * clients + shard_size * (i + 1)]
            client_data, client_label = np.vstack((client_data1, client_data2)), np.hstack((client_label1, client_label2))
            self.datasets.append(TensorDataset(torch.tensor(client_data), torch.tensor(client_label)))

    def get_test_dataset(self):
        return self.test_datasets

    def get_train_dataset(self):
        return self.datasets


if __name__ == '__main__':
    mnist = MNIST(50, False)
