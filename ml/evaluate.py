"""
Evaluation framework for MarketTransformer.

Metrics:
1. Per-class precision / recall / F1
2. Directional accuracy (% of BUY signals where price went up)
3. Simulated PnL with Sharpe ratio
4. Calibration analysis (confidence vs actual accuracy)
5. Per-symbol breakdown

Usage:
    python ml/evaluate.py                         # evaluate saved model on dataset
    python ml/evaluate.py --model-dir ml/output   # explicit path
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import classification_report, confusion_matrix
from train import FEATURE_COLS, SequenceDataset, MarketTransformer
from torch.utils.data import DataLoader
from sklearn.preprocessing import StandardScaler


def load_model(model_dir):
    config_path = os.path.join(model_dir, "config.json")
    model_path = os.path.join(model_dir, "model.pt")

    with open(config_path) as f:
        config = json.load(f)

    model = MarketTransformer(
        n_features=config["n_features"],
        d_model=config["d_model"],
        n_heads=config["n_heads"],
        n_layers=config["n_layers"],
        d_ff=config["d_ff"],
        n_classes=config["n_classes"],
        dropout=0.0,
        seq_len=config["seq_len"],
    )
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model, config


def get_predictions(model, dataloader, device="cpu"):
    all_preds = []
    all_probs = []
    all_labels = []

    n_batches = len(dataloader)
    with torch.no_grad():
        for i, (x, y) in enumerate(dataloader):
            x = x.to(device)
            logits = model(x)
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            preds = np.argmax(probs, axis=1)
            all_preds.extend(preds)
            all_probs.extend(probs)
            all_labels.extend(y.numpy())
            if (i + 1) % 50 == 0 or i == n_batches - 1:
                print(f"  batch {i+1}/{n_batches}", flush=True)

    return np.array(all_preds), np.array(all_probs), np.array(all_labels)


def eval_classification(preds, labels, n_classes):
    label_names = ["SELL", "BUY"] if n_classes == 2 else ["SELL", "HOLD", "BUY"]
    present = sorted(set(labels) | set(preds))
    present_names = [label_names[i] for i in present if i < len(label_names)]
    print("\n" + "=" * 60)
    print("1. CLASSIFICATION REPORT")
    print("=" * 60)
    print(classification_report(labels, preds, labels=present, target_names=present_names, digits=3))
    print("Confusion Matrix:")
    cm = confusion_matrix(labels, preds)
    print(f"{'':>8}", end="")
    for name in label_names:
        print(f"{name:>8}", end="")
    print()
    for i, row in enumerate(cm):
        print(f"{label_names[i]:>8}", end="")
        for v in row:
            print(f"{v:>8}", end="")
        print()


def eval_directional_accuracy(preds, labels, fwd_24bar, n_classes):
    """Directional accuracy using 24-bar forward return (matches label horizon)."""
    print("\n" + "=" * 60)
    print("2. DIRECTIONAL ACCURACY (24-bar horizon)")
    print("=" * 60)

    buy_mask  = preds == (1 if n_classes == 2 else 2)
    sell_mask = preds == 0

    if buy_mask.sum() > 0:
        buy_correct = (fwd_24bar[buy_mask] > 0).mean()
        buy_avg = fwd_24bar[buy_mask].mean()
        print(f"  BUY signals:  {buy_mask.sum():>6} | 24h dir acc: {buy_correct:.1%} | avg 24h return: {buy_avg:+.4f}")

    if sell_mask.sum() > 0:
        sell_correct = (fwd_24bar[sell_mask] < 0).mean()
        sell_avg = fwd_24bar[sell_mask].mean()
        print(f"  SELL signals: {sell_mask.sum():>6} | 24h dir acc: {sell_correct:.1%} | avg 24h return: {sell_avg:+.4f}")

    total = buy_mask.sum() + sell_mask.sum()
    if total > 0:
        correct = (fwd_24bar[buy_mask] > 0).sum() + (fwd_24bar[sell_mask] < 0).sum()
        print(f"  Overall 24h directional accuracy: {correct / total:.1%}")


def _tpsl_backtest(preds, probs, closes_val, n_classes,
                   tp_pct=3.0, sl_pct=1.5, horizon=24,
                   conf_threshold=0.0, fee_pct=0.04):
    """Simulate TP/SL execution bar-by-bar on the val close prices.

    For each signal:
    - Enter at close of signal bar
    - Each subsequent bar: check if TP or SL hit using high/low proxied from close
    - If neither hit within horizon bars, exit at horizon close
    - Apply round-trip fee
    Returns list of trade PnL percentages.
    """
    trades = []
    n = len(closes_val)

    for i in range(n):
        conf = probs[i].max()
        if conf < conf_threshold:
            continue

        pred = preds[i]
        is_buy = (pred == 1 if n_classes == 2 else pred == 2)
        is_sell = (pred == 0)
        if not is_buy and not is_sell:
            continue

        entry = closes_val[i]
        if entry <= 0:
            continue

        tp_price = entry * (1 + tp_pct / 100) if is_buy else entry * (1 - tp_pct / 100)
        sl_price = entry * (1 - sl_pct / 100) if is_buy else entry * (1 + sl_pct / 100)

        result_pct = None
        for j in range(i + 1, min(i + horizon + 1, n)):
            price = closes_val[j]
            if is_buy:
                if price >= tp_price:
                    result_pct = tp_pct
                    break
                elif price <= sl_price:
                    result_pct = -sl_pct
                    break
            else:
                if price <= tp_price:
                    result_pct = tp_pct
                    break
                elif price >= sl_price:
                    result_pct = -sl_pct
                    break

        if result_pct is None:
            # Timeout: exit at horizon price
            exit_price = closes_val[min(i + horizon, n - 1)]
            result_pct = ((exit_price / entry) - 1) * 100 * (1 if is_buy else -1)

        # Deduct round-trip fee
        result_pct -= fee_pct * 2
        trades.append(result_pct)

    return np.array(trades)


def eval_simulated_pnl(preds, probs, closes_val, n_classes,
                       tp_pct=3.0, sl_pct=1.5, horizon=24, fee_pct=0.04):
    print("\n" + "=" * 60)
    print(f"3. TP/SL BACKTEST (TP={tp_pct}% SL={sl_pct}% horizon={horizon}h fee={fee_pct*2:.2f}% RT)")
    print("=" * 60)

    for min_conf, label in [(0.0, "All signals"), (0.60, "Conf ≥ 60%"), (0.65, "Conf ≥ 65%")]:
        trades = _tpsl_backtest(preds, probs, closes_val, n_classes,
                                tp_pct=tp_pct, sl_pct=sl_pct, horizon=horizon,
                                conf_threshold=min_conf, fee_pct=fee_pct)
        if len(trades) == 0:
            print(f"  {label}: no trades")
            continue

        wins   = trades[trades > 0]
        losses = trades[trades <= 0]
        total_pnl = trades.sum()
        win_rate = len(wins) / len(trades)
        avg_trade = trades.mean()
        std_trade = trades.std()
        sharpe = (avg_trade / max(std_trade, 1e-9)) * np.sqrt(8760 / max(horizon, 1))
        pf = wins.sum() / max(abs(losses.sum()), 1e-9) if len(losses) > 0 else float('inf')

        print(f"\n  [{label}]  trades={len(trades):,}")
        print(f"    Win rate:      {win_rate:.1%}")
        print(f"    Avg trade:     {avg_trade:+.3f}%")
        print(f"    Total PnL:     {total_pnl:+.1f}%")
        print(f"    Profit factor: {pf:.2f}")
        print(f"    Sharpe:        {sharpe:+.2f}")
        print(f"    Avg win:       {wins.mean():+.3f}%" if len(wins) else "    Avg win: —")
        print(f"    Avg loss:      {losses.mean():+.3f}%" if len(losses) else "    Avg loss: —")


def eval_calibration(probs, labels, n_bins=10):
    print("\n" + "=" * 60)
    print("4. CALIBRATION (confidence vs actual accuracy)")
    print("=" * 60)

    confidences = probs.max(axis=1)
    preds = probs.argmax(axis=1)
    correct = (preds == labels).astype(float)

    bin_edges = np.linspace(0, 1, n_bins + 1)
    print(f"  {'Bin':>12} {'Count':>8} {'Avg Conf':>10} {'Accuracy':>10} {'Gap':>8}")
    print(f"  {'-'*48}")

    for i in range(n_bins):
        mask = (confidences >= bin_edges[i]) & (confidences < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        avg_conf = confidences[mask].mean()
        acc = correct[mask].mean()
        gap = avg_conf - acc
        print(f"  {bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}  {mask.sum():>8} {avg_conf:>10.3f} {acc:>10.3f} {gap:>+8.3f}")

    # Expected Calibration Error
    ece = 0
    for i in range(n_bins):
        mask = (confidences >= bin_edges[i]) & (confidences < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        avg_conf = confidences[mask].mean()
        acc = correct[mask].mean()
        ece += mask.sum() * abs(avg_conf - acc)
    ece /= len(labels)
    print(f"\n  Expected Calibration Error (ECE): {ece:.4f}")


def eval_per_symbol(dataset, preds, probs, labels, fwd_24bar, n_classes, seq_len):
    print("\n" + "=" * 60)
    print("5. PER-SYMBOL BREAKDOWN (24-bar horizon)")
    print("=" * 60)
    forward_returns = fwd_24bar  # alias for clarity

    symbols = dataset["symbol"].values[seq_len:]
    unique_symbols = sorted(set(symbols))

    if n_classes == 2:
        label_names = {0: "SELL", 1: "BUY"}
    else:
        label_names = {0: "SELL", 1: "HOLD", 2: "BUY"}

    print(f"  {'Symbol':<16} {'Acc':>6} {'DirAcc':>7} {'Sharpe':>7} {'Samples':>8} {'Pred Dist':>20}")
    print(f"  {'-'*64}")

    for sym in unique_symbols:
        mask = symbols == sym
        if mask.sum() < 10:
            continue

        sym_preds = preds[mask]
        sym_labels = labels[mask]
        sym_fwd = forward_returns[mask]

        acc = (sym_preds == sym_labels).mean()

        # Directional accuracy
        if n_classes == 2:
            buy_m = sym_preds == 1
            sell_m = sym_preds == 0
        else:
            buy_m = sym_preds == 2
            sell_m = sym_preds == 0

        dir_correct = 0
        dir_total = 0
        if buy_m.sum() > 0:
            dir_correct += (sym_fwd[buy_m] > 0).sum()
            dir_total += buy_m.sum()
        if sell_m.sum() > 0:
            dir_correct += (sym_fwd[sell_m] < 0).sum()
            dir_total += sell_m.sum()
        dir_acc = dir_correct / max(dir_total, 1)

        # Sharpe
        positions = np.where(sym_preds == (1 if n_classes == 2 else 2), 1.0,
                             np.where(sym_preds == 0, -1.0, 0.0))
        pnl = positions * sym_fwd
        sharpe = (pnl.mean() / max(pnl.std(), 1e-9)) * np.sqrt(8760)

        # Prediction distribution
        pred_dist = ", ".join(f"{label_names[k]}:{(sym_preds == k).sum()}" for k in sorted(label_names))

        print(f"  {sym:<16} {acc:>5.1%} {dir_acc:>6.1%} {sharpe:>+7.2f} {mask.sum():>8} {pred_dist:>20}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=str, default="ml/output")
    parser.add_argument("--data-dir", type=str, default="ml")
    parser.add_argument("--val-months", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=512)
    args = parser.parse_args()

    # Load model
    model, config = load_model(args.model_dir)
    seq_len = config["seq_len"]
    n_classes = config["n_classes"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    print(f"Model: {config['n_features']} features, {n_classes} classes, seq_len={seq_len}")
    print(f"Best training val acc: {config.get('best_val_acc', 'N/A')}")

    # Load dataset
    csv_files = [f for f in os.listdir(args.data_dir) if f.endswith(".csv")]
    dfs = [pd.read_csv(os.path.join(args.data_dir, f)) for f in csv_files]
    df = pd.concat(dfs, ignore_index=True)

    feature_cols = config.get("feature_cols", FEATURE_COLS)
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        print(f"WARNING: {len(missing)} features missing from dataset (filled with 0): {missing}")
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
    elif "ts" in df.columns:
        df = df.sort_values("ts").reset_index(drop=True)

    features = df[feature_cols].values.astype(np.float32)
    labels = df["label"].values.astype(np.int64)

    # Time-based split: last val_pct of each symbol's chronological data → val
    import datetime
    ts_col = "timestamp" if "timestamp" in df.columns else ("ts" if "ts" in df.columns else None)
    timestamps = df[ts_col].values if ts_col else np.arange(len(df), dtype=np.int64)
    symbols_col = df["symbol"].values if "symbol" in df.columns else np.full(len(df), "ALL")

    val_pct = args.val_months / 18.0  # 4 months out of 18 ≈ 22%
    val_pct = min(max(val_pct, 0.15), 0.30)  # clamp 15-30%

    train_mask = np.zeros(len(df), dtype=bool)
    val_mask   = np.zeros(len(df), dtype=bool)
    for sym in np.unique(symbols_col):
        idx = np.where(symbols_col == sym)[0]
        sorted_idx = idx[np.argsort(timestamps[idx])]
        split = int(len(sorted_idx) * (1 - val_pct))
        train_mask[sorted_idx[:split]] = True
        val_mask[sorted_idx[split:]]   = True

    import datetime as dt
    ts_min = dt.datetime.utcfromtimestamp(timestamps[val_mask].min() / 1000).date()
    print(f"Val period: {ts_min} → now ({val_mask.sum():,} samples, {val_mask.mean()*100:.0f}% of data)")

    # Scale using saved scaler params — dimensions must match feature_cols
    scaler_mean = np.array(config["scaler"]["mean"], dtype=np.float32)
    scaler_scale = np.array(config["scaler"]["scale"], dtype=np.float32)
    n_feat = features.shape[1]
    if len(scaler_mean) != n_feat:
        print(f"WARNING: scaler dim ({len(scaler_mean)}) != feature dim ({n_feat}), re-fitting scaler on train split")
        from sklearn.preprocessing import StandardScaler as SS
        sc = SS()
        sc.fit(features[train_mask])
        features = sc.transform(features)
    else:
        features = (features - scaler_mean) / np.maximum(scaler_scale, 1e-9)
    features = np.clip(features, -5.0, 5.0)

    val_features = features[val_mask]
    val_labels = labels[val_mask]
    val_df = df[val_mask].reset_index(drop=True)

    horizon = 24
    has_close = "close" in df.columns

    if has_close:
        closes_all = df["close"].values.astype(np.float64)
    else:
        # Reconstruct per-symbol close from cumulative returns
        # Start each symbol at 1000 (arbitrary base)
        closes_all = np.zeros(len(df))
        for sym in np.unique(df["symbol"].values if "symbol" in df.columns else ["ALL"]):
            if "symbol" in df.columns:
                idx = np.where(df["symbol"].values == sym)[0]
            else:
                idx = np.arange(len(df))
            ret = df["returns"].values[idx]
            price = np.cumprod(1 + np.nan_to_num(ret)) * 1000
            closes_all[idx] = price

    # 24-bar forward return per row (within same symbol to avoid cross-symbol leakage)
    fwd_24 = np.zeros(len(closes_all))
    sym_col = df["symbol"].values if "symbol" in df.columns else np.full(len(df), "ALL")
    for sym in np.unique(sym_col):
        idx = np.where(sym_col == sym)[0]
        c = closes_all[idx]
        fr = np.zeros(len(c))
        fr[:-horizon] = c[horizon:] / np.maximum(c[:-horizon], 1e-9) - 1
        fwd_24[idx] = fr

    val_fwd_24 = fwd_24[val_mask]
    val_closes = closes_all[val_mask]

    val_ds = SequenceDataset(val_features, val_labels, seq_len=seq_len)
    val_dl = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    preds, probs, true_labels = get_predictions(model, val_dl, device)

    # Trim arrays to match SequenceDataset offset (removes first seq_len rows)
    val_fwd_24_trimmed = val_fwd_24[seq_len:len(preds) + seq_len]
    val_closes_trimmed = val_closes[seq_len:len(preds) + seq_len]

    # Run all evaluations
    eval_classification(preds, true_labels, n_classes)
    eval_directional_accuracy(preds, true_labels, val_fwd_24_trimmed, n_classes)
    eval_simulated_pnl(preds, probs, val_closes_trimmed, n_classes,
                       tp_pct=3.0, sl_pct=1.5, horizon=horizon)
    eval_calibration(probs, true_labels)
    eval_per_symbol(val_df, preds, probs, true_labels, val_fwd_24_trimmed, n_classes, seq_len)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    acc = (preds == true_labels).mean()
    print(f"  Val accuracy:        {acc:.1%}")
    print(f"  Val samples:         {len(true_labels):,}")
    print(f"  Majority baseline:   {max(np.bincount(true_labels)) / len(true_labels):.1%}")
    edge = acc - max(np.bincount(true_labels)) / len(true_labels)
    print(f"  Edge over baseline:  {edge:+.1%}")


if __name__ == "__main__":
    main()
