import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import numpy as np
from torch.nn import Parameter

class MaskedLinear(nn.Module):
    def __init__(self, in_features, out_features, bias=True):
        super(MaskedLinear, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.bias_check = bias
        self.weight = Parameter(torch.Tensor(out_features, in_features))
        self.mask = Parameter(torch.ones([out_features, in_features]), requires_grad=False)
        if bias:
            self.bias = Parameter(torch.Tensor(out_features))
        else:
            self.register_parameter('bias', None)
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
        if self.bias_check:
            fan_in, _ = nn.init._calculate_fan_in_and_fan_out(self.weight)
            bound = 1 / math.sqrt(fan_in)
            nn.init.uniform_(self.bias, -bound, bound)
        nn.init.ones_(self.mask)

    def forward(self, input):
        return F.linear(input, self.weight * self.mask, self.bias)

    def prune(self, threshold, k):
        weight_dev = self.weight.device
        mask_dev = self.mask.device
        tensor = self.weight.data.cpu().numpy()
        mask = self.mask.data.cpu().numpy()
        new_mask = np.where(abs(tensor) < threshold, 0, mask)
        nz_count = np.count_nonzero(new_mask)
        if k <= nz_count / (self.in_features * self.out_features):
            self.weight.data = torch.from_numpy(tensor * new_mask).to(weight_dev)
            self.mask.data = torch.from_numpy(new_mask).to(mask_dev)
            return True
        return False

class CustomGRU(nn.Module):
    def __init__(self, input_size, hidden_size, bias=True, batch_first=True):
        super(CustomGRU, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.batch_first = batch_first

        self.update_gate = MaskedLinear(input_size + hidden_size, hidden_size, bias=bias)
        self.reset_gate = MaskedLinear(input_size + hidden_size, hidden_size, bias=bias)
        self.new_memory = MaskedLinear(input_size + hidden_size, hidden_size, bias=bias)

    def forward(self, x, hx=None):
        if self.batch_first:
            x = x.transpose(0, 1) # (seq_len, batch, input_dim)

        seq_len, batch_size, _ = x.size()
        if hx is None:
            hx = torch.zeros(batch_size, self.hidden_size, device=x.device)

        output = []
        for t in range(seq_len):
            xt = x[t]
            combined = torch.cat((xt, hx), dim=1)
            z_t = torch.sigmoid(self.update_gate(combined))
            r_t = torch.sigmoid(self.reset_gate(combined))
            combined_reset = torch.cat((xt, r_t * hx), dim=1)
            n_t = torch.tanh(self.new_memory(combined_reset))
            hx = (1 - z_t) * n_t + z_t * hx
            output.append(hx)

        output = torch.stack(output, dim=0)
        if self.batch_first:
            output = output.transpose(0, 1)

        ht = hx.unsqueeze(0)
        return output, ht

class MaskedAttention(nn.Module):
    def __init__(self, hidden_dim, attention_dim):
        super(MaskedAttention, self).__init__()
        self.query = MaskedLinear(hidden_dim, attention_dim)
        self.key = MaskedLinear(hidden_dim, attention_dim)
        self.value = MaskedLinear(hidden_dim, attention_dim)
        self.context_vector = MaskedLinear(attention_dim, 1, bias=False)

    def forward(self, hidden_states):
        query = self.query(hidden_states)
        key = self.key(hidden_states)
        value = self.value(hidden_states)
        attn_scores = torch.tanh(query + key)
        attn_scores = self.context_vector(attn_scores).squeeze(-1)
        attn_weights = F.softmax(attn_scores, dim=-1)
        weighted_hidden_states = value * attn_weights.unsqueeze(-1)
        context_vector = weighted_hidden_states.sum(dim=1)
        return context_vector

class PruningModule(nn.Module):
    def prune_by_std(self, s, k):
        for name, module in self.named_modules():
            if isinstance(module, (MaskedLinear, CustomGRU, MaskedAttention)):
                self._prune_weights(module, s, k, name)

    def _prune_weights(self, module, s, k, name):
        for attr_name in ['weight_ih', 'weight_hh', 'weight']:
            if hasattr(module, attr_name):
                weight = getattr(module, attr_name)
                threshold = np.std(weight.data.abs().cpu().numpy()) * s
                print(f'Pruning {attr_name} in {name} (threshold={threshold:.6f})')
                while not module.prune(threshold, k):
                    threshold *= 0.99

class AttentionGRU(PruningModule):
    def __init__(self, input_dim=52, hidden_dim=128, attention_dim=32, output_dim=4):
        super(AttentionGRU, self).__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.attention_dim = attention_dim
        self.output_dim = output_dim

        self.gru = CustomGRU(input_dim, hidden_dim, batch_first=True)
        self.attention = MaskedAttention(hidden_dim, attention_dim)
        self.fc = MaskedLinear(attention_dim, output_dim)
        self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        gru_out, _ = self.gru(x)
        context_vector = self.attention(gru_out)
        context_vector = self.dropout(context_vector)
        output = self.fc(context_vector)
        return output

def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
