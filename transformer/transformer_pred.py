# Reference: 
# codebase: http://nlp.seas.harvard.edu/2018/04/03/attention.html
# torchtext load pretrained embeddings: http://anie.me/On-Torchtext/

# Prelims:
# pip install http://download.pytorch.org/whl/cu80/torch-0.3.0.post4-cp36-cp36m-linux_x86_64.whl numpy matplotlib spacy torchtext seaborn 
# python -m spacy download en 

# Train:
# python annotated_transformer.py

# Evaluate:
# python ../evaluation/gleu.py -s source.txt -r target.txt --hyp pred.txt

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import math, copy, time
from torch.autograd import Variable

from torchtext import data, datasets
import spacy

import os
import sys
import random

from Model import MyIterator, make_model, batch_size_fn

def main():
    BOS_WORD = '<s>'
    EOS_WORD = '</s>'
    BLANK_WORD = "<blank>"

    # EMB_DIM should be multiple of 8, look at MultiHeadedAttention
    EMB = 'bow'
    # EMB = 'glove.6B.200d'
    EMB_DIM = 512
    BATCH_SIZE = 2500

    # GPU to use
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    # device = ("cpu")

    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    src_dir = os.path.join(root_dir, 'data/src')
    test_dir = os.path.join(root_dir, 'data/test')
    eval_dir = os.path.join(root_dir, 'data/eval')
    model_path = os.path.join(root_dir, 'data/models', EMB + '.transformer.pt')
    vocab_path = os.path.join(root_dir, 'data/models', 'english.vocab')

    if not os.path.exists(eval_dir):
        os.makedirs(eval_dir)

    #####################
    #   Data Loading    #
    #####################
    spacy_en = spacy.load('en')

    def tokenize_en(text):
        return [tok.text for tok in spacy_en.tokenizer(text)]

    TEXT = data.Field(tokenize=tokenize_en, init_token = BOS_WORD,
                     eos_token = EOS_WORD, pad_token=BLANK_WORD)
    TEXT.vocab = torch.load(vocab_path)
    test = datasets.TranslationDataset(path=os.path.join(src_dir, 'lang8.test'), 
            exts=('.src', '.trg'), fields=(TEXT, TEXT))
    test_iter = MyIterator(test, batch_size=BATCH_SIZE, device=device,
                            repeat=False, sort_key=lambda x: (len(x.src), len(x.trg)),
                            batch_size_fn=batch_size_fn, train=False)

    random_idx = random.randint(0, len(test) - 1)
    print(test[random_idx].src)
    print(test[random_idx].trg)

    #####################
    #   Word Embedding  #
    #####################

    weights = None
    # glove embedding
    if 'glove' in EMB:
        weights = TEXT.vocab.vectors
        EMB_DIM = TEXT.vocab.vectors.shape[1]
    # TODO elmo embedding
    elif 'emlo' in EMB: pass
    # TODO bert embedding

    ##########################
    #      Translation       #
    ##########################
    model = make_model(len(TEXT.vocab), d_model=EMB_DIM, emb_weight=weights, N=6)
    model_weights = torch.load(model_path)
    model.load_state_dict(model_weights)
    model.to(device)

    f_src = open(os.path.join(eval_dir, 'lang8.eval.src'), 'w+')
    f_trg = open(os.path.join(eval_dir, 'lang8.eval.trg'), 'w+')
    f_pred = open(os.path.join(eval_dir, 'lang8.eval.pred'), 'w+')
    
    for i, batch in enumerate(test_iter):
        # source
        src = batch.src.transpose(0, 1)[:1]
        source = ""
        for i in range(1, batch.src.size(0)):
            sym = TEXT.vocab.itos[batch.src.data[i, 0]]
            if sym == "</s>": break
            source += sym + " "
        source += '\n'
        if '<unk>' in source: continue

        # target 
        target = ""
        for i in range(1, batch.trg.size(0)):
            sym = TEXT.vocab.itos[batch.trg.data[i, 0]]
            if sym == "</s>": break
            target += sym + " "
        target += '\n'
        if '<unk>' in target: continue

        # translation 
        src_mask = (src != TEXT.vocab.stoi["<blank>"]).unsqueeze(-2)
        out = greedy_decode(model, src, src_mask, 
                            max_len=60, start_symbol=TEXT.vocab.stoi["<s>"])
        pred = ""
        for i in range(1, out.size(1)):
            sym = TEXT.vocab.itos[out[0, i]]
            if sym == "</s>": break
            pred += sym + " "
        pred += '\n'

        print("Source:", source, end='')
        print("Target:", target, end='')
        print("Translation:", pred)
        f_src.write(source)
        f_trg.write(target)
        f_pred.write(pred)

    f_pred.close()

if __name__ == "__main__":
    main()