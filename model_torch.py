﻿from layers_torch import TemporalDense, LSTM, RNN, TemporalSoftmax, TemporalBatchNorm, DeepMemoryLSTM
import torch, torch.cuda
import numpy as np
from utils import build_logger
import json

class Model:
    def __init__(self, config: dict, layers: dict, device: str) -> None:
        """
        Initializes model. Has all layers setup with internal sizes.

        @param config (dict): dictionary with hyperparameters of the model.
        @param layers (dict): dictionary with model layers.
        @param device (str): device to store tensors.

        """
        self.save_path = config['--to_path']
        self.device = device
        self.preloaded = False
        self.logger = build_logger('output.logger@gmail.com','bcof jupb ugbh vfll')
        self.layers = layers
        self.vocab_size = self.layers[0].in_size 
        
    def load_text(self, file: str, val_size = 0.05) -> None:
        """
        Loads the text file into self.train_text and self.test_text,
        dividing them randomly for every 100 phrases.

        @param file (str): string containing the name of the file that has the text
        @param val_size (int): percentage of text that will go to the validation set
        """
        self.logger.info("Loading text inputs...")

        text = open(f'{file}', 'r',encoding='utf8').read() # should be simple plain text file
        chars = list(set(text))
        data_size, vocab_size = len(text), len(chars)
        print('Data has {} characters, {} unique.'.format(data_size, self.vocab_size))
        #print(self.char_to_ix)
        if self.preloaded == False:
            self.char_to_ix = { ch:i for i,ch in enumerate(chars) }
            self.ix_to_char = { i:ch for i,ch in enumerate(chars) }
        else:
            text = ''.join([ch for ch in text if ch in self.char_to_ix.keys()])

        self.train_text = ''
        self.test_text = ''
        text_phrases = text.split('\n')
        for i in range(len(text_phrases)//100):
            text_to_add = '\n'.join(text_phrases[i * 100: (i+1) * 100])
            if np.random.randint(0,int(1/val_size)) == 0:
                self.test_text += text_to_add
            else:
                self.train_text += text_to_add
        

    def save(self, path:str) -> None:
        """
        Save current model parameters on separate file, to later be loaded.

        @param path (str): file path where model parameters will be saved
        """

        params = []
        for layer in self.layers:
            params.append({key: value.tolist() for key, value in layer.params.items()})
        params.append(self.char_to_ix)
        params = json.dumps(params)
        file = open(path, 'w')
        file.write(params)
        file.close()
     
    def load(self, path:str) -> None:
        """
        Load model params from json file

        @param path (str): file path where model parameters are
        """

        self.preloaded = True
        self.layers = []
        file = open(path, 'r')
        param_list = file.read()
        param_list = json.loads(param_list)
        self.char_to_ix = param_list.pop()
        self.ix_to_char = {i:ch for ch, i in self.char_to_ix.items()}
        for i, param_dict in enumerate(param_list):
            if param_dict['type'] == [4]:
                layer = TemporalSoftmax(device=self.device)
                self.layers.append(layer)
            elif param_dict['type'] == [1]:
                layer = TemporalDense(0, 0, device=self.device)
                layer.params = {key: torch.tensor(value,device=self.device) for key, value in param_list[i].items()}
                self.layers.append(layer)
            elif param_dict['type'] == [2]:
                layer = RNN(0, 0, device=self.device)
                layer.params = {key: torch.tensor(value,device=self.device) for key, value in param_list[i].items()}
                self.layers.append(layer)
            elif param_dict['type'] == [3]:
                layer = LSTM(0, 0, device=self.device)
                layer.params = {key: torch.tensor(value,device=self.device) for key, value in param_list[i].items()}
                self.layers.append(layer)
        #get vocab size from the first dense layer in the loaded model
        self.vocab_size = self.layers[0].params['W'].shape[0]

    def sample(self, seed:str, n_timesteps:int) -> list:
        """
        Generate indexes to test model's generative properties
        Generates list of indexes iteratively, based on initial string (seed)

        @param seed (str): string to start your generation with
        @param n_timesteps (int): number of indexes generated after the end of "seed"

        @returns idxs (list): list with all indexes generated
        """

        # create list with indexes of seed, starting with 0:
        idx = [0]+[self.char_to_ix[ch] for ch in seed]
        
        # create input as one-hot-encoded vector of indexes:
        inputs = torch.zeros((1, len(seed)+1, self.vocab_size),device=(self.device))
        for t, timestep in enumerate(inputs[0]):
            timestep[idx[t]] += 1

    
        # iterate through seed, build hidden and cell states of layers:
        self.a = inputs.clone()
        for layer in self.layers:
            self.a = layer.forward(self.a)


        # get last word for generation ([:,-1] to eliminate the [timesteps] dimension)    
        self.a = self.a[:,-1]
        # create list of all indexes generated (starting by current)
        p = self.a.ravel()
        
        idxs = [torch.distributions.categorical.Categorical(probs = self.a.ravel()).sample().item()]
        # generate text with len = [n_timesteps]
        for t in range(n_timesteps):   
            for layer in self.layers:
                # choose which kind of layer this is
                if layer.params['type'] == 2: # forward step for rnn
                    layer.h, _ = layer.forward_step(self.a, layer.h)
                    self.a = layer.h
                elif layer.params['type'] == 3: # forward step for lstm
                        layer.h, layer.c, _ = layer.forward_step(self.a, layer.h, layer.c)
                        self.a = layer.h
                else: 
                    self.a, _ = layer.forward_step(self.a)
            idx = torch.distributions.categorical.Categorical(probs = self.a.ravel()).sample().item()
            self.a = torch.zeros_like(self.a, device=(self.device)) 
            self.a[0,idx] += 1
            idxs.append(idx)
        txt = ''.join(self.ix_to_char[ix] for ix in idxs)
        
        return txt

    def test(self, n_timesteps:int, batch_size:int) -> int:
        """
        Runs batched forward passes through the entire validation dataset (self.test_text)
        and computes the average of the test loss.

        @param n_timesteps (int): number of timesteps each batch goes through
        @param batch_size (int): number of elements (word or character) per batch

        @returns torch.mean(test_losses) (int): mean of all test losses computed in this test
        """
        test_pointer = 0
        test_losses = []

        # go through entire validation set:
        while test_pointer + 2 * (n_timesteps * batch_size ) + 1 < len(self.test_text):
            inputs, _, target_idxs = self._get_batch(self.test_text, test_pointer, n_timesteps, batch_size)
                    
            a = inputs.clone()

            # forward pass
            for layer in self.layers:
                a = layer.forward(a)

            # calculate loss
            _, loss = self.layers[-1].backward(target_idxs,a)

            test_losses.append(loss.item())
            test_pointer += n_timesteps * batch_size # move data pointer
        return np.mean(test_losses)

    def _get_batch(self, text:str, pointer:int, n_timesteps:int, batch_size:int) -> tuple:
        """
        Runs batched forward passes through the entire validation dataset (self.test_text)
        and computes the average of the test loss.

        @param text (str): entire corpus of text
        @param pointer (int): index (location in the text) in current epoch
        @param n_timesteps (int): number of characters per sequence
        @param batch_size (int): number of sequences per batch

        @returns inputs (torch.tensor): one_hot_encoded vector of inputs (shape N,T,Vocab)
        @returns inputs_idxs (torch.tensor): vector of input indexes (shape N,T)
        @returns target_idxs (torch.tensor): vector of target indexes (shape N,T)
        """
        N, T, V = batch_size, n_timesteps, self.vocab_size 
        input_idxs = torch.zeros([N,T], device=(self.device),dtype=torch.int64)
        target_idxs = torch.zeros([N,T], device=(self.device),dtype=torch.int64)
        # for every sequence in batch, store the indexes of every word
        for b in range(N):
            input_idxs[b,:] = torch.tensor([self.char_to_ix[ch] for ch in text[
                pointer + ((b)*T): pointer + ((b+1)*T)
                ]],device=self.device,dtype=torch.int64)
            target_idxs[b,:] = torch.tensor([int(self.char_to_ix[ch]) for ch in text[
                1 + pointer + ((b)*T): 1 + pointer + ((b+1)*T)
                ]],device=self.device,dtype=torch.int64)
        
        # one-hot-encode indexes
        inputs = torch.zeros((N, T, V),device=self.device)
        inputs.scatter_(2,input_idxs.unsqueeze(dim=2),torch.ones(N,T,V,device=self.device)) 

        return inputs, input_idxs, target_idxs
    
    def train(self, n_iter: int, n_timesteps: int, batch_size: int,learning_rate=1e-3,regularization=1e-3,patience = 7) -> None: 
        """
        Trains model, performing forward passes, backward passes, and optimization steps.

        @param n_iter (int): total batches the model will go through in training 
        @param n_timesteps (int): number of timesteps each batch will go through in training
        @param batch_size (int): number of phrases with shape [n_timesteps, self.vocab_size] in each batch
        @param learning_rate (int): hyperparameter which defines "size" of each optimization step
        @param regularization (int): hyperparameter which defines amount of L2 regularization
        @param patience (int): number of iterations after each learning_rate decay (*0.9) until next can happen;
        learning_rate decay happens when a smooth_loss is larger than 
        """   
        self.logger.info("Training")
        pointer, decay_counter = 0, 0
        losses = [10e6]
        test_losses = [10e6]

        for layer in self.layers:
            layer.initialize_optimizer(learning_rate, regularization)

        smooth_loss = -np.log(1.0/self.vocab_size)
        for t in range(n_iter):
            
            if pointer + (n_timesteps * batch_size ) + 1 >= len(self.train_text): 
                pointer = np.random.randint(0,n_timesteps//2) # start from random point of data
            
            inputs, _, target_idxs = self._get_batch(self.train_text, pointer, n_timesteps, batch_size)
            
            a = inputs.clone()
              
            # forward pass (with residual connections)
            for layer in self.layers[:-1]:
                #a = layer.forward(a)
                # layer.initialize_optimizer(learning_rate, regularization)
                new_a = layer.forward(a)
                # if the layer does not change input shape, use residuals
                if new_a.shape == a.shape:
                    a = a + new_a
                else:
                    a = new_a

            # calculate loss
            a = self.layers[-1].forward(a)
            dz, loss = self.layers[-1].backward(target_idxs,a)

            # backward pass (with residual connections)
            self.layers.reverse()
            for layer in self.layers[1:]:
                #dz = layer.backward(dz)
                new_dz = layer.backward(dz)
                # if the layer does not change input shape, use residuals
                if new_dz.shape == dz.shape:
                    dz = dz + new_dz
                else:
                    dz = new_dz
                # update step
                layer.optimize()
            self.layers.reverse()
            smooth_loss = 0.99 * smooth_loss + 0.01 * loss
            # sample from the model now and then
            if t % 150 == 0:
                txt = self.sample('. ', 500)
                print("#=========#\n{}\n#=========#".format(txt))
                test_loss = self.test(n_timesteps, batch_size)
                print(f'iter {t}, loss: {smooth_loss}, test_loss {test_loss}') 
                self.logger.info(f'iter {t}, loss: {smooth_loss}, test_loss {test_loss}')

                if test_loss > test_losses[-1] and decay_counter >= patience:
                    for layer in self.layers:
                        layer.config['learning_rate'] *= 0.94
                    print("BREAK - learning_rate @ layer[0]: {}".format(self.layers[0].config['learning_rate']))
                    decay_counter = 0
                if test_loss <= min(test_losses):
                    print(f'saving into {self.save_path}')
                    self.save(self.save_path)
                decay_counter += 1
                losses.append(smooth_loss)
                test_losses.append(test_loss)

            pointer += n_timesteps * batch_size # move data pointer
            
        





