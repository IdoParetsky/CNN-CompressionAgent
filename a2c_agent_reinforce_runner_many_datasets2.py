# from NetworkFeatureExtration.src.ModelClasses.NetX.netX import NetX - must be import!!!!
import glob
import os
import time
from datetime import datetime
import sys
import argparse
from os.path import join

import numpy as np
import pandas as pd
import torch
from pandas import DataFrame
from sklearn.model_selection import train_test_split
from torch import nn
from NetworkFeatureExtration.src.ModelWithRows import ModelWithRows
from src.A2C_Agent_Reinforce import A2C_Agent_Reinforce

from src.Configuration.ConfigurationValues import ConfigurationValues
from src.Configuration.StaticConf import StaticConf
from NetworkFeatureExtration.src.ModelClasses.NetX.netX import NetX
from src.NetworkEnv import NetworkEnv
from src.utils import print_flush, load_models_path, get_model_layers_str


def init_conf_values(compression_rates_dict, num_epoch=100, is_learn_new_layers_only=False,
                     total_allowed_accuracy_reduction=1, increase_loops_from_1_to_4=False, prune=False):
    if not torch.cuda.is_available():
        sys.exit("GPU was not allocated!!!!")

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print_flush(f"device is {device}")
    print_flush(f"device name is {torch.cuda.get_device_name(0)}")

    num_actions = len(compression_rates_dict)
    MAX_TIME_TO_RUN = 60 * 60 * 24 * 1.5
    cv = ConfigurationValues(device, compression_rates_dict=compression_rates_dict, num_actions=num_actions,
                             num_epoch=num_epoch,
                             is_learn_new_layers_only=is_learn_new_layers_only,
                             total_allowed_accuracy_reduction=total_allowed_accuracy_reduction,
                             increase_loops_from_1_to_4=increase_loops_from_1_to_4,
                             prune=prune,
                             MAX_TIME_TO_RUN=MAX_TIME_TO_RUN)
    StaticConf(cv)


torch.manual_seed(0)
np.random.seed(0)


def evaluate_model(mode, base_path, agent):
    models_path = load_models_path(base_path, mode)
    env = NetworkEnv(models_path, StaticConf.getInstance().conf_values.increase_loops_from_1_to_4)
    compression_rates_dict = {
        0: 1,
        1: 0.9,
        2: 0.8,
        3: 0.7,
        4: 0.6
    }

    results = DataFrame(columns=['model', 'new_acc', 'origin_acc', 'new_param',
                                 'origin_param', 'new_model_arch', 'origin_model_arch',
                                 'evaluation_time'])

    for i in range(len(env.all_networks)):
        print_flush(f"network index {i}")
        state = env.reset()
        done = False

        t_start = time.time()
        origin_lh = env.create_learning_handler(env.loaded_model.model)
        origin_acc = origin_lh.evaluate_model()
        origin_params = env.calc_num_parameters(env.loaded_model.model, StaticConf.getInstance().conf_values.prune)

        while not done:
            # dist, value = agent.actor_critic_model(state)
            value = agent.critic_model(state)
            dist = agent.actor_model(state)

            action = dist.sample()
            compression_rate = compression_rates_dict[action.cpu().numpy()[0]]
            next_state, reward, done = env.step(compression_rate)
            state = next_state

        t_end = time.time()

        new_lh = env.create_learning_handler(env.current_model)
        new_acc = new_lh.evaluate_model()
        new_params = env.calc_num_parameters(env.current_model, StaticConf.getInstance().conf_values.prune)


        model_name = env.all_networks[env.net_order[env.curr_net_index - 1]][1]

        new_model_with_rows = ModelWithRows(env.current_model)

        results = results.append({'model': model_name,
                                  'new_acc': new_acc,
                                  'origin_acc': origin_acc,
                                  'new_param': new_params,
                                  'origin_param': origin_params,
                                  'new_model_arch': get_model_layers_str(env.current_model),
                                  'origin_model_arch': get_model_layers_str(env.loaded_model.model),
                                  'evaluation_time': t_end - t_start}, ignore_index=True)

    return results


def main(fold, is_learn_new_layers_only, test_name,
         total_allowed_accuracy_reduction, is_to_split_cv=False, increase_loops_from_1_to_4=False,
         prune=False, dataset_split_seed=0):
    base_path = f"./OneDatasetLearning/Classification/"
    datasets = list(map(os.path.basename, glob.glob(join(base_path, "*"))))
    np.random.shuffle(datasets)
    num_of_folds = 6

    flatten = lambda l: [item for sublist in l for item in sublist]

    all_datasets_splitted = [datasets[i:i + num_of_folds] for i in range(0, len(datasets), num_of_folds)]
    test_datasets = all_datasets_splitted[fold]
    train_datasets = flatten([*all_datasets_splitted[:fold], *all_datasets_splitted[fold + 1:]])

    # train_datasets, test_datasets = train_test_split(datasets, test_size = 0.2, random_state=dataset_split_seed)
    print_flush(f"train datasets =  {train_datasets}")
    print_flush(f"test datasets = {test_datasets}")

    actions = {
        0: 1,
        1: 0.9,
        2: 0.8,
        3: 0.7,
        4: 0.6
    }

    if prune:
        num_epoch = 10
    else:
        num_epoch = 100

    init_conf_values(actions, is_learn_new_layers_only=is_learn_new_layers_only, num_epoch=num_epoch,
                     total_allowed_accuracy_reduction=total_allowed_accuracy_reduction,
                     increase_loops_from_1_to_4=increase_loops_from_1_to_4, prune=prune)

    train_models_path = [load_models_path(join(base_path, dataset_name), 'train') for dataset_name in train_datasets]
    test_models_path = [load_models_path(join(base_path, dataset_name), 'train') for dataset_name in test_datasets]
    flatten = lambda l: [item for sublist in l for item in sublist]

    train_models_path = flatten(train_models_path)
    test_models_path = flatten(test_models_path)

    agent = A2C_Agent_Reinforce(train_models_path, test_name)
    print_flush("Starting training")
    agent.train()
    print_flush("Done training")

    print_flush("Starting evaluate train datasets")

    for d in train_datasets:
        mode = 'test'
        results = evaluate_model(mode, join(base_path, d), agent)
        results.to_csv(f"./models/Reinforce_One_Dataset/results_{d}_{test_name}_{mode}_trained_dataset.csv")

        mode = 'train'
        results = evaluate_model(mode, join(base_path, d), agent)
        results.to_csv(f"./models/Reinforce_One_Dataset/results_{d}_{test_name}_{mode}_trained_dataset.csv")

    print_flush("Starting evaluate test datasets")
    for d in test_datasets:
        mode = 'all'
        results = evaluate_model(mode, join(base_path, d), agent)
        results.to_csv(f"./models/Reinforce_One_Dataset/results_{d}_{test_name}_{mode}_unseen_dataset.csv")

        # mode = 'train'
        # results = evaluate_model(mode, join(base_path, d), agent)
        # results.to_csv(f"./models/Reinforce_One_Dataset/results_{d}_{test_name}_{mode}_unseen_dataset.csv")


def extract_args_from_cmd():
    parser = argparse.ArgumentParser(description='')
    # parser.add_argument('--test_name', type=str)
    # parser.add_argument('--dataset_name', type=str)
    parser.add_argument('--learn_new_layers_only', type=bool, const=True, default=False, nargs='?')
    parser.add_argument('--split', type=bool, const=True, default=True, nargs='?')
    parser.add_argument('--allowed_reduction_acc', type=int, default=5, nargs='?')
    parser.add_argument('--increase_loops_from_1_to_4', type=bool, const=True, default=True, nargs='?')
    parser.add_argument('--prune', type=bool, const=True, default=True, nargs='?')
    parser.add_argument('--fold', type=int,  default=5, nargs='?')

    args = parser.parse_args()
    return args

if __name__ == "__main__":
    print_flush("Starting scripttt")
    args = extract_args_from_cmd()
    print_flush(args)
    with_loops = '_with_loop' if args.increase_loops_from_1_to_4 else ""
    pruned = '_pruned' if args.prune else ""
    fold = f'_fold{args.fold}'
    test_name = f'All_Datasets_Agent_learn_new_layers_only_{args.learn_new_layers_only}_acc_reduction_{args.allowed_reduction_acc}{with_loops}{pruned}{fold}'
    print_flush(test_name)
    main(fold=args.fold, is_learn_new_layers_only=args.learn_new_layers_only, test_name=test_name,
         is_to_split_cv=args.split,
         total_allowed_accuracy_reduction=args.allowed_reduction_acc,
         increase_loops_from_1_to_4=args.increase_loops_from_1_to_4,
         prune=args.prune)
