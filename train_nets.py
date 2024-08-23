import os

import torch
import numpy as np
# from NetworkFeatureExtration.src.ModelClasses.NetX.netX import NetX - should be import!!!!
from NetworkFeatureExtration.src.ModelClasses.NetX.netX import NetX
from NetworkFeatureExtration.src.main import load_checkpoint, load_model_and_data
from src.A2C_Agent_Reinforce import A2C_Agent_Reinforce
from src.Configuration.ConfigurationValues import ConfigurationValues
from src.Configuration.StaticConf import StaticConf
from src.Model.ActorCritic import ActorCritic
from src.NetworkEnv import NetworkEnv
import pandas as pd
from a2c_combined_agent_reinforce_runner import init_conf_values, load_models_path
import cProfile, pstats
from io import StringIO


torch.manual_seed(0)
np.random.seed(0)

num_epoch = 100
init_conf_values(num_epoch=num_epoch, is_learn_new_layers_only=True)
models_path = load_models_path('./OneDatasetLearning/Classification/mfeat-karhunen/', 'all')

x = models_path[0][0]
y = models_path[0][0].replace('X_train', 'Y_train')

from datetime import datetime

name = 'train_all_model_epochs_{}'.format(num_epoch)
data = []


pr = cProfile.Profile()
pr.enable()

for model_path in models_path[0][1]:
    start = datetime.now()

    print(model_path)
    env = NetworkEnv([[x, [model_path]]])
    env.reset()

    learning_handler_prev_model = env.create_learning_handler(env.current_model)
    curr_acc = learning_handler_prev_model.evaluate_model()
    curr_model_data = [model_path, curr_acc]

    env.layer_index = len(env.feature_extractor.model_with_rows.all_rows) - 1

    # while env.layer_index < len:
    env.step(1)
    learning_handler_prev_model = env.create_learning_handler(env.current_model)
    curr_acc = learning_handler_prev_model.evaluate_model()
    curr_model_data.append(curr_acc)

    curr_model_data.insert(1, str(datetime.now() - start))
    data.append(curr_model_data)
    break

pr.disable()
s = StringIO()
sortby = 'cumulative'
ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
ps.print_stats()
print(s.getvalue())


print(curr_model_data)



