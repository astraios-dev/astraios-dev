"""
SageMaker training entry point for MarketTransformer v3.

v3 changes:
- Binary classification (BUY/SELL, no HOLD)
- 21 pruned features (dropped dead OI/LS, redundant pairs)
- Smaller model: d_model=64, 2 heads, 2 layers (less overfitting)
- Focal loss (handles class imbalance better than label-smoothed CE)
- Purged walk-forward CV with embargo (prevents label leakage)
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    # Price action (5)
    "returns",
    "ema_ratio_8", "ema_ratio_21", "ema_ratio_50",
    "close_position",
    # Momentum (4)
    "rsi_14",
    "macd_hist",
    "bb_pct",
    "mom_20",
    # Volatility (3)
    "atr_norm",
    "rolling_vol_5", "rolling_vol_20",
    # Volume (3)
    "vol_ratio",
    "taker_buy_ratio", "taker_buy_pressure",
    # Lagged returns (2)
    "ret_lag_1", "ret_lag_3",
    # Microstructure — funding only (2)
    "funding_rate", "funding_rate_ma8",
    # Cross-asset context (4)
    "btc_returns", "btc_mom_5",
    "btc_vol_ratio", "btc_trend",
    # Regime features (3)
    "vol_regime", "trend_strength", "price_vs_sma200",
    # Correlation + funding divergence (2)
    "btc_corr_20", "funding_divergence",
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


class FocalLoss(nn.Module):
    """Cost-sensitive focal loss.

    Combines focal weighting (down-weights easy examples) with asymmetric
    cost: confident wrong predictions are penalised with an extra `cost_wrong`
    multiplier. This matters for trading — a high-confidence wrong signal is
    worse than an uncertain one.
    """
    def __init__(self, alpha=None, gamma=2.0, cost_wrong=2.0):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.cost_wrong = cost_wrong

    def forward(self, logits, targets):
        ce = F.cross_entropy(logits, targets, weight=self.alpha, reduction='none')
        pt = torch.exp(-ce)
        # High confidence (pt close to 0 means wrong with high confidence)
        # pt close to 1 means correct with high confidence (easy)
        focal_weight = (1 - pt) ** self.gamma
        # Extra penalty when confident AND wrong: pt < 0.3 means wrong with >70% confidence
        confident_wrong = (pt < 0.3).float()
        cost_weight = 1.0 + (self.cost_wrong - 1.0) * confident_wrong
        return (focal_weight * cost_weight * ce).mean()


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
    """MarketTransformer v4 — CNN front-end + Transformer encoder.

    1D CNN with kernels 3/5/7 extracts local candlestick patterns
    before the Transformer sees the sequence. This gives the model
    an inductive bias for short-term price structure (hammers,
    engulfing, 3-bar momentum bursts) that a pure attention mechanism
    struggles to learn from raw features.
    """
    def __init__(self, n_features, d_model, n_heads, n_layers, d_ff, n_classes, dropout, seq_len):
        super().__init__()

        # CNN front-end: three parallel convolutions, outputs concatenated → d_model
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
        # x: (batch, seq_len, n_features)
        xT = x.transpose(1, 2)  # → (batch, n_features, seq_len) for Conv1d
        x3 = self.cnn3(xT)
        x5 = self.cnn5(xT)
        x7 = self.cnn7(xT)
        x = torch.cat([x3, x5, x7], dim=1).transpose(1, 2)  # → (batch, seq_len, d_model)
        x = self.pos_enc(x)
        x = self.dropout(x)
        x = self.encoder(x)
        x = self.norm(x[:, -1, :])
        return self.head(x)


def per_symbol_walk_forward_splits(symbols, timestamps, n_folds=3, embargo_bars=24,
                                    train_pct=0.70, val_pct=0.20):
    """Per-symbol expanding walk-forward CV with embargo gap.

    For each symbol independently:
      - Sort rows chronologically
      - Train window: first train_pct of that symbol's rows
      - Embargo: `embargo_bars` rows dropped between train and val
      - Val window: next val_pct rows
      - Remaining: held out as test (not used during training)

    For n_folds > 1, the val window slides backward producing n_folds folds.
    Masks are combined across all symbols per fold.

    This prevents cross-symbol contamination: ETHUSDT val data is never
    in the same fold as BTCUSDT training data from an overlapping time window.
    """
    unique_symbols = np.unique(symbols)
    n = len(symbols)
    all_splits = []

    for fold in range(n_folds):
        train_mask = np.zeros(n, dtype=bool)
        val_mask = np.zeros(n, dtype=bool)
        fold_train_n = fold_val_n = 0

        for sym in unique_symbols:
            sym_idx = np.where(symbols == sym)[0]
            sym_ts = timestamps[sym_idx]
            order = np.argsort(sym_ts)
            sym_idx_sorted = sym_idx[order]
            m = len(sym_idx_sorted)

            if m < 200:
                continue

            # Expanding window: each fold shifts val window earlier
            val_end   = int(m * (train_pct + val_pct))
            val_start = int(m * train_pct)

            # Slide val window back for later folds
            window_size = val_end - val_start
            val_end   -= fold * (window_size // n_folds)
            val_start -= fold * (window_size // n_folds)

            if val_start <= embargo_bars or val_end > m:
                continue

            train_end = val_start - embargo_bars

            if train_end < 50:
                continue

            train_mask[sym_idx_sorted[:train_end]] = True
            val_mask[sym_idx_sorted[val_start:val_end]] = True
            fold_train_n += train_end
            fold_val_n += (val_end - val_start)

        if fold_val_n == 0:
            break

        all_splits.append((train_mask, val_mask))
        print(f"  Fold {fold+1}: train={fold_train_n:,} val={fold_val_n:,} embargo={embargo_bars} bars/symbol")

    return all_splits


def train_fold(features, labels, train_mask, val_mask, args, device, fold_num):
    """Train one fold and return best val accuracy."""
    scaler = StandardScaler()
    scaler.fit(features[train_mask])
    scaled = scaler.transform(features)
    scaled = np.clip(scaled, -5.0, 5.0)

    train_x, train_y = scaled[train_mask], labels[train_mask]
    val_x, val_y = scaled[val_mask], labels[val_mask]

    train_ds = SequenceDataset(train_x, train_y, seq_len=args.seq_len)
    val_ds = SequenceDataset(val_x, val_y, seq_len=args.seq_len)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)
    val_dl = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    n_classes = int(labels.max()) + 1
    class_counts = np.bincount(train_y, minlength=n_classes).astype(np.float32)
    class_weights = 1.0 / np.maximum(class_counts, 1)
    class_weights = class_weights / class_weights.sum() * n_classes
    weight_tensor = torch.FloatTensor(class_weights).to(device)

    model = MarketTransformer(
        n_features=len(FEATURE_COLS),
        d_model=args.d_model,
        n_heads=args.n_heads,
        n_layers=args.n_layers,
        d_ff=args.d_ff,
        n_classes=n_classes,
        dropout=args.dropout,
        seq_len=args.seq_len,
    ).to(device)

    criterion = FocalLoss(alpha=weight_tensor, gamma=2.0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=args.lr * 0.01
    )

    best_val_acc = 0
    best_state = None
    patience_counter = 0

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
        val_loss_avg   = val_loss   / max(val_total, 1)
        train_acc = train_correct / max(train_total, 1)
        val_acc   = val_correct   / max(val_total, 1)
        print(f"  [Fold {fold_num}] Epoch {epoch+1:3d}/{args.epochs}  "
              f"train_loss={train_loss_avg:.4f} acc={train_acc:.3f}  "
              f"val_loss={val_loss_avg:.4f} acc={val_acc:.3f}")

        if np.isnan(train_loss_avg) or np.isnan(val_loss_avg):
            print("  NaN detected — stopping fold early.")
            break

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"  Early stopping at epoch {epoch+1} (patience={args.patience})")
                break

    return best_val_acc, best_state, scaler


def train(args):
    data_dir  = args.data_dir
    model_dir = args.model_dir

    csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    dfs = [pd.read_csv(os.path.join(data_dir, f)) for f in csv_files]
    df = pd.concat(dfs, ignore_index=True)

    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    df = df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    ts_col = "timestamp" if "timestamp" in df.columns else ("ts" if "ts" in df.columns else None)
    if ts_col:
        df = df.sort_values(ts_col).reset_index(drop=True)

    features   = df[FEATURE_COLS].values.astype(np.float32)
    labels     = df["label"].values.astype(np.int64)
    timestamps = df[ts_col].values if ts_col else np.arange(len(df), dtype=np.int64)
    symbols    = df["symbol"].values if "symbol" in df.columns else np.full(len(df), "UNK")

    n_classes = int(labels.max()) + 1
    class_counts = np.bincount(labels, minlength=n_classes)
    print(f"Dataset: {len(df):,} rows, {len(FEATURE_COLS)} features, {n_classes} classes")
    print(f"Class distribution: {dict(zip(range(n_classes), class_counts.tolist()))}")
    print(f"Symbols: {np.unique(symbols).tolist()}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Per-symbol walk-forward CV
    print(f"\nPer-symbol walk-forward CV ({args.n_folds} folds, embargo={args.embargo_bars} bars/symbol):")
    splits = per_symbol_walk_forward_splits(symbols, timestamps, n_folds=args.n_folds,
                                             embargo_bars=args.embargo_bars)

    fold_results = []
    best_overall_acc = 0
    best_overall_state = None
    best_overall_scaler = None

    for i, (train_mask, val_mask) in enumerate(splits):
        print(f"\n--- Fold {i+1}/{len(splits)} ---")
        acc, state, scaler = train_fold(features, labels, train_mask, val_mask, args, device, i+1)
        fold_results.append(acc)
        print(f"  Fold {i+1} best val acc: {acc:.3f}")

        if acc > best_overall_acc:
            best_overall_acc = acc
            best_overall_state = state
            best_overall_scaler = scaler

    avg_acc = np.mean(fold_results)
    std_acc = np.std(fold_results)
    print(f"\n{'='*50}")
    print(f"Walk-forward CV results: {avg_acc:.3f} ± {std_acc:.3f}")
    print(f"Per-fold: {[f'{a:.3f}' for a in fold_results]}")
    print(f"Best fold: {best_overall_acc:.3f}")

    # Save best model
    if best_overall_state is not None:
        torch.save(best_overall_state, os.path.join(model_dir, "model.pt"))

    config = {
        "n_features": len(FEATURE_COLS),
        "d_model":    args.d_model,
        "n_heads":    args.n_heads,
        "n_layers":   args.n_layers,
        "d_ff":       args.d_ff,
        "n_classes":  n_classes,
        "dropout":    args.dropout,
        "seq_len":    args.seq_len,
        "feature_cols": FEATURE_COLS,
        "scaler": {
            "mean":  best_overall_scaler.mean_.tolist(),
            "scale": best_overall_scaler.scale_.tolist(),
        },
        "best_val_acc": best_overall_acc,
        "cv_mean_acc": float(avg_acc),
        "cv_std_acc": float(std_acc),
        "cv_fold_accs": [float(a) for a in fold_results],
    }
    with open(os.path.join(model_dir, "config.json"), "w") as f:
        json.dump(config, f)

    print(f"\nSaved model + config to {model_dir}")
    print(f"Best val accuracy: {best_overall_acc:.3f}")
    print(f"CV mean ± std: {avg_acc:.3f} ± {std_acc:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",       type=int,   default=40)
    parser.add_argument("--batch-size",   type=int,   default=256)
    parser.add_argument("--lr",           type=float, default=3e-4)
    parser.add_argument("--seq-len",      type=int,   default=48)
    parser.add_argument("--d-model",      type=int,   default=64)
    parser.add_argument("--n-heads",      type=int,   default=2)
    parser.add_argument("--n-layers",     type=int,   default=2)
    parser.add_argument("--d-ff",         type=int,   default=128)
    parser.add_argument("--dropout",      type=float, default=0.15)
    parser.add_argument("--patience",     type=int,   default=8)
    parser.add_argument("--n-folds",      type=int,   default=3)
    parser.add_argument("--embargo-bars", type=int,   default=24)
    parser.add_argument("--val-months",   type=int,   default=4)
    parser.add_argument("--data-dir",     type=str,   default=os.environ.get("SM_CHANNEL_TRAINING", "ml"))
    parser.add_argument("--model-dir",    type=str,   default=os.environ.get("SM_MODEL_DIR", "ml/output"))
    args = parser.parse_args()
    os.makedirs(args.model_dir, exist_ok=True)
    train(args)
