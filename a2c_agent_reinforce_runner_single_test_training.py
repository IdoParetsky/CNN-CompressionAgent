# from NetworkFeatureExtration.src.ModelClasses.NetX.netX import NetX - must be import!!!!

import os
from datetime import datetime
import sys
import argparse
from os.path import basename

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
from src.utils import load_models_path


def init_conf_values(compression_rates_dict, num_epoch=100, is_learn_new_layers_only=False,
                     total_allowed_accuracy_reduction=1, increase_loops_from_1_to_4=False):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    num_actions = len(compression_rates_dict)
    cv = ConfigurationValues(device, compression_rates_dict=compression_rates_dict, num_actions=num_actions,
                             num_epoch=num_epoch,
                             is_learn_new_layers_only=is_learn_new_layers_only,
                             total_allowed_accuracy_reduction=total_allowed_accuracy_reduction,
                             increase_loops_from_1_to_4=increase_loops_from_1_to_4)
    StaticConf(cv)


torch.manual_seed(0)
np.random.seed(0)


def get_linear_layer(row):
    for l in row:
        if type(l) is nn.Linear:
            return l


def get_model_layers(model):
    new_model_with_rows = ModelWithRows(model)
    linear_layers = [(get_linear_layer(x).in_features, get_linear_layer(x).out_features) for x in
                     new_model_with_rows.all_rows]
    return str(linear_layers)


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
                                 'origin_param', 'new_model_arch', 'origin_model_arch'])

    for i in range(len(env.all_networks)):
        print(i)
        state = env.reset()
        done = False

        while not done:
            # dist, value = agent.actor_critic_model(state)
            value = agent.critic_model(state)
            dist = agent.actor_model(state)

            action = dist.sample()
            compression_rate = compression_rates_dict[action.cpu().numpy()[0]]
            next_state, reward, done = env.step(compression_rate)
            state = next_state

        new_lh = env.create_learning_handler(env.current_model)
        origin_lh = env.create_learning_handler(env.loaded_model.model)

        new_acc = new_lh.evaluate_model()
        origin_acc = origin_lh.evaluate_model()

        new_params = env.calc_num_parameters(env.current_model)
        origin_params = env.calc_num_parameters(env.loaded_model.model)

        model_name = env.all_networks[env.net_order[env.curr_net_index - 1]][1]

        new_model_with_rows = ModelWithRows(env.current_model)

        results = results.append({'model': model_name,
                                  'new_acc': new_acc,
                                  'origin_acc': origin_acc,
                                  'new_param': new_params,
                                  'origin_param': origin_params,
                                  'new_model_arch': get_model_layers(env.current_model),
                                  'origin_model_arch': get_model_layers(env.loaded_model.model)}, ignore_index=True)

    return results


def main(dataset_name, is_learn_new_layers_only, test_name,
         total_allowed_accuracy_reduction, is_to_split_cv=False, increase_loops_from_1_to_4 = False):
    actions = {
        0: 1,
        1: 0.9,
        2: 0.8,
        3: 0.7,
        4: 0.6
    }
    base_path = f"./OneDatasetLearning/Classification/{dataset_name}/"

    init_conf_values(actions, is_learn_new_layers_only=is_learn_new_layers_only, num_epoch=100,
                     total_allowed_accuracy_reduction=total_allowed_accuracy_reduction,
                     increase_loops_from_1_to_4=increase_loops_from_1_to_4)
    models_path = load_models_path(base_path, 'test')

    for curr_test_model in models_path[0][1]:
        curr_model_to_train = (models_path[0][0], [curr_test_model])
        agent = A2C_Agent_Reinforce([curr_model_to_train], test_name + '_single_test_')
        agent.train()

        mode = 'test'
        results = evaluate_model(mode, base_path, agent)
        model_name = (basename(curr_test_model)).split(".")[0]
        results.to_csv(f"./models/Reinforce_One_Dataset/results_{test_name}_single_test_{model_name}_{mode}.csv")


def extract_args_from_cmd():
    parser = argparse.ArgumentParser(description='')
    # parser.add_argument('--test_name', type=str)
    parser.add_argument('--dataset_name', type=str)
    parser.add_argument('--learn_new_layers_only', type=bool, const=True, default=False, nargs='?')
    parser.add_argument('--allowed_reduction_acc', type=int, nargs='?')
    parser.add_argument('--increase_loops_from_1_to_4', type=bool, const=True, default=False, nargs='?')

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = extract_args_from_cmd()
    with_loops = '_with_loop' if args.increase_loops_from_1_to_4 else ""
    test_name = f'Agent_{args.dataset_name}_learn_new_layers_only_{args.learn_new_layers_only}_acc_reduction_{args.allowed_reduction_acc}{with_loops}'
    main(dataset_name=args.dataset_name, is_learn_new_layers_only=args.learn_new_layers_only,test_name=test_name,
         is_to_split_cv=False,
         total_allowed_accuracy_reduction=args.allowed_reduction_acc,
         increase_loops_from_1_to_4=args.increase_loops_from_1_to_4)
