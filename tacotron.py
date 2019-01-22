import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.nn.utils as utils
from hparams import hparams as hp
import numpy as np
from ZoneoutRNN import ZoneoutRNN
import math

class Tacotron(nn.Module):
    def __init__(self, encoder, decoder, postnet, max_length=1000):
        super(Tacotron, self).__init__()
        self.encoder = encoder
        self.decoder = decoder
        self.postnet = postnet
        self.max_length = max_length

    def forward(self, input_group, mel_group = None, linear_target=None, stop_token_target=None):
        #input_seqs [batch_size, seq_lens]
        input_seqs, max_input_len = input_group
        mel_target, max_target_len = mel_group
        batch_size = input_seqs.size(0)
        #mel_target [batch_size,  max_target_length / hp.outputs_per_step, decoder_output_size]
        if mel_target is None or max_target_len is None:
            assert hp.use_gta_mode == False, 'if use_gta_mode == True, please provide with target'
            max_target_len = math.ceil(self.max_length / hp.outputs_per_step)
        else:
            max_target_len = math.ceil(max_target_len / hp.outputs_per_step)
        self.encoder.initialize(batch_size, max_input_len)
        encoder_outputs = self.encoder(input_seqs)
        self.decoder.attn.initialize(batch_size, max_input_len, encoder_outputs)
        decoder_inputs = torch.zeros(batch_size, 1, self.decoder.prenet_input_size)
        #initial decoder hidden state
        decoder_hidden = torch.zeros(self.decoder.decoder_lstm_layers, batch_size, self.decoder.decoder_lstm_units)
        decoder_cell_state = torch.zeros(self.decoder.decoder_lstm_layers, batch_size, self.decoder.decoder_lstm_units)
        decoder_outputs = torch.zeros(batch_size, max_target_len, self.decoder.decoder_output_size)
        self.postnet.initialize(self.decoder.decoder_output_size, max_target_len)
        stop_token_prediction = torch.zeros(batch_size, max_target_len, hp.outputs_per_step)

        for t in range(max_target_len):
            decoder_output, stop_token_output, decoder_hidden, decoder_cell_state = \
                self.decoder(decoder_inputs, decoder_hidden, decoder_cell_state)
            decoder_outputs[:, t, :] = torch.squeeze(decoder_output, 1)
            stop_token_prediction[:, t, :] = torch.squeeze(stop_token_output, 1)
            if hp.use_gta_mode:
                if hp.teacher_forcing_schema == "full":
                    decoder_inputs = mel_target[:, t:t+1, :]
                elif hp.teacher_forcing_schema == "semi":
                    decoder_inputs = (
                        decoder_output + mel_target[:, t:t+1, :]
                    ) / 2
                elif hp.teacher_forcing_schema == "random":
                    if np.random.random() <= self.teacher_forcing_ratio:
                        decoder_inputs = mel_target[:, t:t+1, :]
                    else:
                        decoder_inputs = decoder_output
        postnet_outputs = self.postnet(decoder_outputs)
        mel_outputs = decoder_outputs + postnet_outputs

        if hp.use_stop_token:
            stop_token_prediction = torch.reshape(stop_token_prediction, [batch_size, -1])




