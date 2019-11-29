# first of all, I think we still need a policy network independently from value. Somehow I think this is the best
# We run MCTS until the end
# We then sample the MCTS timesteps to train the neural network (how many times?)
# Then we repeat. (with new MCTS tree? right?)
# We need to design the asynchronous behavior.

from mcts import MCTS, TimeStep
from neuralnetwork import NoPolicy, PaperLoss
import random
import torch
import torch.optim
import torch.nn as nn
import os
from pathlib import Path
from os.path import abspath
import datetime


class AlphaZero:
    """
    Use MCTS to generate g number of games
    Train based on these games with repeatedly sampled time steps
    Refresh the g number of games, repeat
    """

    def __init__(self, model_name, is_cuda=True):
        self.model_name = model_name
        self.nn = NoPolicy()
        self.is_cuda=is_cuda
        if self.is_cuda:
            self.nn=self.nn.cuda()
        # TODO
        self.loss = PaperLoss()
        self.optim = torch.optim.Adam(self.nn.parameters(), weight_decay=0.01)
        self.batch_size = 16
        # time steps contain up to self.game_size different games.
        self.time_steps = []
        self.game_size = 4
        self.total_epochs = 20
        self.train_period = 2000
        self.validation_period = 100
        self.print_period = 10
        self.save_period = 1000
        self.log_file = "log/" + self.model_name + "_" + datetime_filename() + ".txt"
        self.refresh_period=10

    def refresh_games(self):
        with torch.no_grad():
            self.nn.eval()
            self.time_steps = []
            for i in range(self.game_size):
                mcts = MCTS(self.nn, self.is_cuda)
                mcts.play_until_terminal()
                self.time_steps += mcts.time_steps

    def train_one_round(self):
        self.nn.train()
        # sample self.batch_size number of time steps, bundle them together
        self.batch_tss = random.choices(self.time_steps, k=self.batch_size)
        input, target = self.time_steps_to_tensor(self.batch_tss)
        output = self.nn(input)
        loss = self.loss(output, target)
        loss.backward()
        self.optim.step()
        return loss.data

    def validation(self):
        with torch.no_grad():
            self.nn.eval()
            validation_time_steps = []
            for i in range(self.game_size):
                mcts = MCTS(self.nn)
                mcts.play_until_terminal()
                validation_time_steps += mcts.time_steps
            self.batch_tss = random.choices(validation_time_steps, k=self.batch_size)
            input, target = self.time_steps_to_tensor(self.batch_tss)
            output = self.nn(input)
            loss = self.loss(output, target)
            return loss.data

    def time_steps_to_tensor(self, batch_tss):
        # TODO
        return None

    def train(self):
        for epoch in range(self.total_epochs):
            for ti in range(self.train_period):
                if ti % self.refresh_period==0:
                    self.refresh_games()
                train_loss = self.train_one_round()
                if ti % self.print_period == 0:
                    self.log_print(
                        "%14s " % self.model_name +
                        "train epoch %4d, batch %4d. running loss: %.5f" %
                        (epoch, ti, train_loss))
                if ti % self.validation_period == 0:
                    self.validation()



    def log_print(self, message):
        string = str(message)
        if self.log_file is not None and self.log_file != False:
            with open(self.log_file, 'a') as handle:
                handle.write(string + '\n')
        print(string)

    def save_model(self, epoch, iteration):

        epoch = int(epoch)
        task_dir = os.path.dirname(abspath(__file__))
        if not os.path.isdir(Path(task_dir) / "saves"):
            os.mkdir(Path(task_dir) / "saves")

        pickle_file = Path(task_dir).joinpath(
            "saves/" + self.model_name + "_" + str(epoch) + "_" + str(iteration) + ".pkl")
        with pickle_file.open('wb') as fhand:
            torch.save((self.nn, self.optim, epoch, iteration), fhand)

        print("saved model", self.model_name, "at", pickle_file)

    def load_model(self, computer, optim, starting_epoch, starting_iteration, model_name):
        task_dir = os.path.dirname(abspath(__file__))
        save_dir = Path(task_dir) / "saves"
        highest_epoch = 0
        highest_iter = 0

        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)

        for child in save_dir.iterdir():
            if child.name.split("_")[0]==model_name:
                epoch = child.name.split("_")[1]
                iteration = child.name.split("_")[2].split('.')[0]
                iteration = int(iteration)
                epoch = int(epoch)
                # some files are open but not written to yet.
                if child.stat().st_size > 20480:
                    if epoch > highest_epoch or (iteration > highest_iter and epoch == highest_epoch):
                        highest_epoch = epoch
                        highest_iter = iteration

        if highest_epoch == 0 and highest_iter == 0:
            print("nothing to load")
            return computer, optim, starting_epoch, starting_iteration

        if starting_epoch == 0 and starting_iteration == 0:
            pickle_file = Path(task_dir).joinpath(
                "saves/" + model_name + "_" + str(highest_epoch) + "_" + str(highest_iter) + ".pkl")
            print("loading model at", pickle_file)
            with pickle_file.open('rb') as pickle_file:
                computer, optim, epoch, iteration = torch.load(pickle_file)
            print('Loaded model at epoch ', highest_epoch, 'iteration', highest_iter)
        else:
            pickle_file = Path(task_dir).joinpath(
                "saves/" + model_name + "_" + str(starting_epoch) + "_" + str(starting_iteration) + ".pkl")
            print("loading model at", pickle_file)
            with pickle_file.open('rb') as pickle_file:
                computer, optim, epoch, iteration = torch.load(pickle_file)
            print('Loaded model at epoch ', starting_epoch, 'iteration', starting_iteration)

        return computer, optim, highest_epoch, highest_iter



def datetime_filename():
    return datetime.datetime.now().strftime("%m_%d_%X")

if __name__ == '__main__':
    az=AlphaZero("first", is_cuda=True)
    az.train()