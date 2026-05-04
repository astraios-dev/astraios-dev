"""
MarketTransformer v4: CNN front-end + Transformer encoder.
Mirrors ml/train.py — keep in sync.
"""

import math
import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=512):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, :x.size(1)]


class MarketTransformer(nn.Module):
    def __init__(
        self,
        n_features=28,
        d_model=64,
        n_heads=2,
        n_layers=2,
        d_ff=128,
        n_classes=2,
        dropout=0.15,
        seq_len=48,
    ):
        super().__init__()

        cnn_out = d_model // 3
        self.cnn3 = nn.Sequential(nn.Conv1d(n_features, cnn_out, kernel_size=3, padding=1), nn.GELU())
        self.cnn5 = nn.Sequential(nn.Conv1d(n_features, cnn_out, kernel_size=5, padding=2), nn.GELU())
        self.cnn7 = nn.Sequential(nn.Conv1d(n_features, d_model - 2 * cnn_out, kernel_size=7, padding=3), nn.GELU())

        self.pos_enc = PositionalEncoding(d_model, max_len=seq_len)
        self.dropout = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_ff,
            dropout=dropout, batch_first=True, activation="gelu",
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.norm    = nn.LayerNorm(d_model)
        self.head    = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, n_classes),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, (nn.Linear, nn.Conv1d)):
                nn.init.xavier_uniform_(m.weight, gain=0.5)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x):
        xT = x.transpose(1, 2)
        x3 = self.cnn3(xT)
        x5 = self.cnn5(xT)
        x7 = self.cnn7(xT)
        x = torch.cat([x3, x5, x7], dim=1).transpose(1, 2)
        x = self.pos_enc(x)
        x = self.dropout(x)
        x = self.encoder(x)
        x = self.norm(x[:, -1, :])
        return self.head(x)
