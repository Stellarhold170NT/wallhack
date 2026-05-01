import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionGRU(nn.Module):
    """Attention-GRU classifier for WiFi CSI activity recognition.

    Adapted from Kang et al. 2025 — replaces CustomGRU with nn.GRU
    (cuDNN accelerated) and MaskedAttention with standard nn.Linear
    additive attention.  No pruning for v1.
    """

    def __init__(
        self,
        input_dim: int = 52,
        hidden_dim: int = 128,
        attention_dim: int = 32,
        output_dim: int = 4,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.attention_dim = attention_dim
        self.output_dim = output_dim

        self.gru = nn.GRU(input_dim, hidden_dim, batch_first=True)

        self.attention = nn.Sequential(
            nn.Linear(hidden_dim, attention_dim),
            nn.Tanh(),
            nn.Linear(attention_dim, 1, bias=False),
        )

        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, time_steps, input_dim)
        gru_out, _ = self.gru(x)                      # (batch, time_steps, hidden_dim)

        attn_scores = self.attention(gru_out)          # (batch, time_steps, 1)
        attn_scores = attn_scores.squeeze(-1)          # (batch, time_steps)
        attn_weights = F.softmax(attn_scores, dim=1)   # (batch, time_steps)

        context = (gru_out * attn_weights.unsqueeze(-1)).sum(dim=1)  # (batch, hidden_dim)

        output = self.fc(context)                      # (batch, output_dim)
        return output


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
