﻿from model_torch import Model 
from argparse import ArgumentParser
import json
import torch, torch.cuda
import os
from utils import _build_config_function

def test_model(args, vocab_size):
    config = args.config(vocab_size, device)
    model = Model(config, vocab_size, save_path='',device=device)
    model.load(f'{PATH}/models/{args.from_path}')
    print(args.seed + model.sample(args.seed,args.sample_size))
   
def train_model(args, vocab_size):
    config = args.config(vocab_size, device)
    model = Model(config, vocab_size, f'{PATH}/models/{args.to_path}', device=device)
    model.load_text(f'{PATH}/data/{args.corpus}')

    config = config['hyperparameters']
    losses = model.train(config['n_iter'],
                        config['n_timesteps'],
                        config['batch_size'],
                        config['learning_rate'],
                        config['regularization'],
                        config['patience'])

def fine_tune(args, vocab_size):
    config = args.config(vocab_size, device)
    model = Model(config, vocab_size, f'{PATH}/models/{args.to_path}', device=device)

    model.load(f'{PATH}/models/{args.from_path}')
    model.load_text(f'{PATH}/data/{args.corpus}')
    config = config['hyperparameters']

    losses = model.train(config['n_iter'],
                        config['n_timesteps'],
                        config['batch_size'],
                        config['learning_rate'],
                        config['regularization'],
                        config['patience'])

def parse_arguments():
    parser = ArgumentParser(description='configuration of runtime application')
    parser.add_argument('--train', action='store_true',
                        help='train the model with provided config file and text corpus')
    parser.add_argument('--fine_tune', action='store_true',
                        help='train the model with provided config file and text corpus')
    parser.add_argument('--test', action='store_true',
                        help='test the model with provided text sample_size (default = 300) and seed')

    parser.add_argument('--config', nargs='?', type=_build_config_function, default=f"{PATH}/config.py",
                        help='path to configuration file for fine tuning/training the model')
    parser.add_argument('--corpus', nargs='?', type=str, default=f"{PATH}/data/sanderson.txt",
                        help='path to text corpus used to fine tune/train model')
    parser.add_argument('--to_path', nargs='?', type=str, default=f"{PATH}/models/model_01.json",
                        help='path to .json file where model will be stored')

    parser.add_argument('--sample_size',nargs='?', type=int, default=300,
                        help='number of characters/tokens to sample when generating test phrase')
    parser.add_argument('--seed',nargs='?', default="Shallan opened her book and began to read it, and then ",
                        help='used seed')
    parser.add_argument('--from_path',nargs='?', default=f"{PATH}/models/model_01.json",
                        help='path to file with model parameters to be loaded')

    args = parser.parse_args()

    return args

PATH = os.getcwd()

if torch.cuda.is_available():
    cuda_device = torch.device("cuda:0")
    device = cuda_device
    print ("Device: cuda")
    torch.cuda.set_device(device)
# elif torch.backends.mps.is_available():
#     device = torch.device('mps:0')
#     print ("Device: mps")
else:
    device = 'cpu'
    print ("CUDA device not found, using CPU")
args = parse_arguments()

if args.train:
    vocab_size = len(set((open(f'{PATH}/data/{args.corpus}','r',encoding='utf8')).read()))
    train_model(args, vocab_size)
if args.fine_tune:
    vocab_size_to = len(set((open(f'{PATH}/data/{args.corpus}','r',encoding='utf8')).read()))
    vocab_size_from = len(json.loads(open(f'{PATH}/models/{args.from_path}','r').read()).pop())
    vocab_size = max(vocab_size_to,vocab_size_from)
    fine_tune(args, vocab_size)
    
if args.test:
    vocab_size = len(json.loads(open(f'{PATH}/models/{args.from_path}','r').read()).pop())
    test_model(args, vocab_size)

