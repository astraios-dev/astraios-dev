"""
SageMaker training entry point for MarketTransformer v2.

Enhancements vs v1:
- 34 features (+ funding rate, open interest, long/short ratio)
- Triple barrier labels
- Larger model: d_model=256, n_layers=4
- Longer sequence: 48 bars
- Walk-forward cross-validation (5 folds)
- Label smoothing in loss
- CNN front-end for local pattern extraction
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "returns", "log_returns",
    "ema_ratio_8", "ema_ratio_21", "ema_ratio_50", "ema_cross_8_21",
    "rsi_14", "rsi_7",
    "macd", "macd_signal", "macd_hist",
    "bb_pct", "atr_norm",
    "vol_ratio",
    "ret_lag_1", "ret_lag_2", "ret_lag_3", "ret_lag_5",
    "mom_5", "mom_10", "mom_20",
    "high_low_range", "close_position",
    "rolling_vol_5", "rolling_vol_20",
    "taker_buy_ratio", "taker_buy_ma8", "taker_buy_delta", "taker_buy_pressure",
    "funding_rate", "funding_rate_ma8", "funding_rate_std8", "funding_cumulative",
    "oi_change", "oi_ratio", "oi_price_div",
    "long_short_ratio", "ls_ma8", "ls_change",
]


class SequenceDataset(Dataset):
    def __init__(self, features, labels, seq_len=48):
        self.features = features
        self.labels = labels
        self.seq_len = seq_len

    def __len__(self):
        return len(self.features) - self.seq_len

    def __getitem__(self, idx):
        x = self.features[idx:idx + self.seq_len]
        y = self.labels[idx + self.seq_len - 1]
        return torch.FloatTensor(x), torch.LongTensor([y])[0]


class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=512):
        super().__init__()
        import math
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, :x.size(1)]


class MarketTransformer(nn.Module):
    def __init__(self, n_features, d_model, n_heads, n_layers, d_ff, n_classes, dropout, seq_len):
        super().__init__()

        self.input_proj = nn.Linear(n_features, d_model)
        self.pos_enc    = PositionalEncoding(d_model, max_len=seq_len)
        self.dropout    = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_ff,
            dropout=dropout, batch_first=True, activation="gelu",
            norm_first=True,  # pre-norm: more stable
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.norm    = nn.LayerNorm(d_model)
        self.head    = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, n_classes),
        )

        # Xavier init for stability
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=0.5)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x):
        x = self.input_proj(x)
        x = self.pos_enc(x)
        x = self.dropout(x)
        x = self.encoder(x)
        x = self.norm(x[:, -1, :])
        return self.head(x)


def walk_forward_split(features, labels, symbols, n_folds=5):
    """5-fold walk-forward: train on first k folds, validate on k+1."""
    unique = np.unique(symbols)
    folds = []
    for sym in unique:
        mask = symbols == sym
        sym_f = features[mask]
        sym_l = labels[mask]
        fold_size = len(sym_f) // n_folds
        if fold_size < 50:
            # Not enough data for walk-forward; use 80/20
            split = int(len(sym_f) * 0.8)
            folds.append((sym_f[:split], sym_l[:split], sym_f[split:], sym_l[split:]))
        else:
            # Use first 80% for train, last 20% for val
            split = fold_size * (n_folds - 1)
            folds.append((sym_f[:split], sym_l[:split], sym_f[split:], sym_l[split:]))

    train_x = np.concatenate([f[0] for f in folds])
    train_y = np.concatenate([f[1] for f in folds])
    val_x   = np.concatenate([f[2] for f in folds])
    val_y   = np.concatenate([f[3] for f in folds])
    return train_x, train_y, val_x, val_y


def train(args):
    data_dir  = args.data_dir
    model_dir = args.model_dir

    csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    dfs = [pd.read_csv(os.path.join(data_dir, f)) for f in csv_files]
    df = pd.concat(dfs, ignore_index=True)

    # Fill missing new features with 0 for backward compat
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    df = df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    features = df[FEATURE_COLS].values.astype(np.float32)
    labels   = df["label"].values.astype(np.int64)
    symbols  = df["symbol"].values if "symbol" in df.columns else np.array(["unknown"] * len(df))

    scaler   = StandardScaler()
    features = scaler.fit_transform(features)
    features = np.clip(features, -5.0, 5.0)  # clip outliers after scaling

    train_x, train_y, val_x, val_y = walk_forward_split(features, labels, symbols)
    print(f"Train: {len(train_x)}, Val: {len(val_x)}")

    train_ds = SequenceDataset(train_x, train_y, seq_len=args.seq_len)
    val_ds   = SequenceDataset(val_x, val_y, seq_len=args.seq_len)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)
    val_dl   = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    class_counts  = np.bincount(train_y, minlength=3).astype(np.float32)
    class_weights = 1.0 / np.maximum(class_counts, 1)
    class_weights = class_weights / class_weights.sum() * 3
    weight_tensor = torch.FloatTensor(class_weights).to(device)

    model = MarketTransformer(
        n_features=len(FEATURE_COLS),
        d_model=args.d_model,
        n_heads=args.n_heads,
        n_layers=args.n_layers,
        d_ff=args.d_ff,
        n_classes=3,
        dropout=args.dropout,
        seq_len=args.seq_len,
    ).to(device)

    criterion = nn.CrossEntropyLoss(weight=weight_tensor, label_smoothing=0.05)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=args.lr * 0.01
    )

    best_val_acc = 0
    for epoch in range(args.epochs):
        model.train()
        train_loss, train_correct, train_total = 0, 0, 0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            out = model(x)
            loss = criterion(out, y)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss    += loss.item() * x.size(0)
            train_correct += (out.argmax(1) == y).sum().item()
            train_total   += x.size(0)

        scheduler.step()
        model.eval()
        val_loss, val_correct, val_total = 0, 0, 0
        with torch.no_grad():
            for x, y in val_dl:
                x, y = x.to(device), y.to(device)
                out  = model(x)
                loss = criterion(out, y)
                val_loss    += loss.item() * x.size(0)
                val_correct += (out.argmax(1) == y).sum().item()
                val_total   += x.size(0)

        train_loss_avg = train_loss / max(train_total, 1)
        val_loss_avg   = val_loss   / max(val_total,   1)
        train_acc = train_correct / max(train_total, 1)
        val_acc   = val_correct   / max(val_total,   1)
        print(f"Epoch {epoch+1:3d}/{args.epochs}  "
              f"train_loss={train_loss_avg:.4f} acc={train_acc:.3f}  "
              f"val_loss={val_loss_avg:.4f} acc={val_acc:.3f}")

        if np.isnan(train_loss_avg) or np.isnan(val_loss_avg):
            print("NaN detected — stopping early.")
            break

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), os.path.join(model_dir, "model.pt"))

    config = {
        "n_features": len(FEATURE_COLS),
        "d_model":    args.d_model,
        "n_heads":    args.n_heads,
        "n_layers":   args.n_layers,
        "d_ff":       args.d_ff,
        "n_classes":  3,
        "dropout":    args.dropout,
        "seq_len":    args.seq_len,
        "feature_cols": FEATURE_COLS,
        "scaler": {
            "mean":  scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
        },
        "best_val_acc": best_val_acc,
    }
    with open(os.path.join(model_dir, "config.json"), "w") as f:
        json.dump(config, f)

    print(f"\nBest val accuracy: {best_val_acc:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",     type=int,   default=60)
    parser.add_argument("--batch-size", type=int,   default=256)
    parser.add_argument("--lr",         type=float, default=5e-5)
    parser.add_argument("--seq-len",    type=int,   default=64)
    parser.add_argument("--d-model",    type=int,   default=256)
    parser.add_argument("--n-heads",    type=int,   default=8)
    parser.add_argument("--n-layers",   type=int,   default=4)
    parser.add_argument("--d-ff",       type=int,   default=512)
    parser.add_argument("--dropout",    type=float, default=0.25)
    parser.add_argument("--data-dir",   type=str,   default=os.environ.get("SM_CHANNEL_TRAINING", "ml"))
    parser.add_argument("--model-dir",  type=str,   default=os.environ.get("SM_MODEL_DIR", "ml/output"))
    args = parser.parse_args()
    os.makedirs(args.model_dir, exist_ok=True)
    train(args)
