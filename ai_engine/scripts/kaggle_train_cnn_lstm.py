import os
import json
import time
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import matplotlib.pyplot as plt
from sklearn.model_selection import GroupKFold

# ==========================================
# 1. Configuration & Hyperparameters
# ==========================================
CSV_FILE_PATH = 'egypt_solar_data_2018_2026.csv' # Upload this to your Kaggle Notebook!
MODEL_SAVE_PATH = 'cnn_lstm_best.pth'

BATCH_SIZE = 32
EPOCHS = 50
LEARNING_RATE = 1e-3
PATIENCE = 15

# ==========================================
# 2. Data Preparation (From CSV)
# ==========================================
def prepare_data_from_csv(csv_path):
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.lower()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['location_id', 'date'])
    
    # Fill missing values
    df['allsky_sfc_sw_dwn'] = df['allsky_sfc_sw_dwn'].fillna(0.0)
    df['t2m'] = df['t2m'].fillna(25.0)
    df['rh2m'] = df['rh2m'].fillna(40.0)
    df['ws2m'] = df['ws2m'].fillna(3.0)
    # If dust_risk_score isn't in CSV, default to 0.07 (or you can calculate it from your clustering)
    if 'dust_risk_score' not in df.columns:
        df['dust_risk_score'] = 0.07
    else:
        df['dust_risk_score'] = df['dust_risk_score'].fillna(0.07)
    
    X_list, y_list, g_list = [], [], []
    
    # Process by location
    for loc_id, group in df.groupby('location_id'):
        records = group.to_dict('records')
        sequence_length = 365
        n_years = len(records) // sequence_length
        
        for i in range(n_years):
            chunk = records[i * sequence_length: (i + 1) * sequence_length]
            
            # Build Sequence (365, 5)
            seq = np.zeros((365, 5), dtype=np.float32)
            for j, r in enumerate(chunk):
                seq[j, 0] = r['allsky_sfc_sw_dwn']
                seq[j, 1] = r['t2m']
                seq[j, 2] = r['rh2m']
                seq[j, 3] = r['ws2m']
                seq[j, 4] = r['dust_risk_score']
                
            # Compute Monthly target (kWh/kWp/month)
            y_monthly = np.zeros(12, dtype=np.float32)
            monthly_ghi, monthly_temp, monthly_dust, monthly_count = {}, {}, {}, {}
            for r in chunk:
                m = r['date'].month
                monthly_ghi[m] = monthly_ghi.get(m, 0.0) + r['allsky_sfc_sw_dwn']
                monthly_temp.setdefault(m, []).append(r['t2m'])
                monthly_dust.setdefault(m, []).append(r['dust_risk_score'])
                monthly_count[m] = monthly_count.get(m, 0) + 1
                
            for m in range(1, 13):
                if monthly_count.get(m, 0) == 0: continue
                avg_temp = np.mean(monthly_temp[m])
                avg_dust = np.mean(monthly_dust[m])
                total_ghi = monthly_ghi[m]
                
                # Formula: GHI * eff * (1-temp_loss) * (1-dust)
                # We assume eff=0.22, temp_coeff=-0.32%/C
                temp_loss = max(0.0, (avg_temp - 25.0) * 0.32 * 0.01)
                y_monthly[m - 1] = total_ghi * 0.22 * (1.0 - temp_loss) * (1.0 - avg_dust)
                
            X_list.append(seq)
            y_list.append(y_monthly)
            g_list.append(loc_id)
            
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    groups = np.array(g_list, dtype=np.int64)
    
    # Min-Max Normalisation
    for f in range(X.shape[2]):
        fmin = X[:, :, f].min()
        fmax = X[:, :, f].max()
        if fmax - fmin > 1e-9:
            X[:, :, f] = (X[:, :, f] - fmin) / (fmax - fmin)
            
    print(f"Data Prepared: X shape={X.shape}, y shape={y.shape}")
    return X, y, groups

# ==========================================
# 3. Model Architecture
# ==========================================
class AttentionPool(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.norm = nn.LayerNorm(d_model)
        self.query = nn.Parameter(torch.randn(1, 1, d_model))

    def forward(self, x):
        q = self.query.expand(x.size(0), -1, -1)
        out, weights = self.attn(q, x, x)
        out = self.norm(out + q)
        return out.squeeze(1), weights

class SolarYieldCNNLSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(5, 64, kernel_size=7, padding=3),
            nn.GELU(),
            nn.MaxPool1d(2),
            nn.BatchNorm1d(64),
            nn.Conv1d(64, 128, kernel_size=14, padding=7),
            nn.GELU(),
            nn.MaxPool1d(2),
            nn.BatchNorm1d(128)
        )
        self.lstm = nn.LSTM(128, 128, num_layers=2, batch_first=True,
                            bidirectional=True, dropout=0.3)
        self.attn_pool = AttentionPool(256, 4, 0.3)
        self.head = nn.Sequential(
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(128, 12)
        )
        self.last_attn_weights = None

    def forward(self, x):
        c = self.cnn(x.permute(0, 2, 1)) 
        c = c.permute(0, 2, 1)            
        lstm_out, _ = self.lstm(c)         
        pooled, self.last_attn_weights = self.attn_pool(lstm_out)
        out = self.head(pooled)           
        return out

# ==========================================
# 4. Training Loop
# ==========================================
def train_model():
    X, y, groups = prepare_data_from_csv(CSV_FILE_PATH)
    
    # Train / Val / Test Split using GroupKFold
    gkf = GroupKFold(n_splits=5)
    folds = list(gkf.split(X, y, groups))
    train_idx, val_idx = folds[0]
    
    # Split val_idx into val and test
    mid = len(val_idx) // 2
    test_idx = val_idx[mid:]
    val_idx = val_idx[:mid]
    
    X_train, y_train = torch.tensor(X[train_idx]), torch.tensor(y[train_idx])
    X_val, y_val = torch.tensor(X[val_idx]), torch.tensor(y[val_idx])
    X_test, y_test = torch.tensor(X[test_idx]), torch.tensor(y[test_idx])
    
    train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=BATCH_SIZE)
    test_loader = DataLoader(TensorDataset(X_test, y_test), batch_size=BATCH_SIZE)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    model = SolarYieldCNNLSTM().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    criterion = nn.HuberLoss()
    
    best_val_loss = float('inf')
    patience_counter = 0
    history = {'train_loss': [], 'val_loss': [], 'train_mae': [], 'val_mae': []}
    
    print("\n--- Starting Training ---")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss, train_mae = 0.0, 0.0
        
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            preds = model(bx)
            loss = criterion(preds, by)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * bx.size(0)
            train_mae += torch.abs(preds - by).mean().item() * bx.size(0)
            
        scheduler.step()
        train_loss /= len(train_loader.dataset)
        train_mae /= len(train_loader.dataset)
        
        # Validation
        model.eval()
        val_loss, val_mae = 0.0, 0.0
        with torch.no_grad():
            for bx, by in val_loader:
                bx, by = bx.to(device), by.to(device)
                preds = model(bx)
                loss = criterion(preds, by)
                val_loss += loss.item() * bx.size(0)
                val_mae += torch.abs(preds - by).mean().item() * bx.size(0)
                
        val_loss /= len(val_loader.dataset)
        val_mae /= len(val_loader.dataset)
        
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['train_mae'].append(train_mae)
        history['val_mae'].append(val_mae)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
            best_str = "(New Best!)"
        else:
            patience_counter += 1
            best_str = ""
            
        if epoch % 5 == 0 or epoch == 1:
            print(f"Epoch {epoch:03d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val MAE: {val_mae:.2f} {best_str}")
            
        if patience_counter >= PATIENCE:
            print(f"Early stopping triggered at epoch {epoch}")
            break
            
    print("\n--- Training Complete ---")
    
    # ==========================================
    # 5. Evaluation & Visualisation
    # ==========================================
    model.load_state_dict(torch.load(MODEL_SAVE_PATH))
    model.eval()
    
    preds_list, targets_list = [], []
    with torch.no_grad():
        for bx, by in test_loader:
            bx = bx.to(device)
            preds = model(bx).cpu().numpy()
            preds_list.append(preds)
            targets_list.append(by.numpy())
            
    all_preds = np.concatenate(preds_list, axis=0).flatten()
    all_targets = np.concatenate(targets_list, axis=0).flatten()
    
    mae = np.mean(np.abs(all_targets - all_preds))
    rmse = np.sqrt(np.mean((all_targets - all_preds)**2))
    print(f"\n[Test Metrics] MAE: {mae:.2f} kWh/kWp | RMSE: {rmse:.2f} kWh/kWp")
    
    # ── Plots ──
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    
    # Loss Curve
    axes[0].plot(history['train_loss'], label='Train Loss')
    axes[0].plot(history['val_loss'], label='Val Loss')
    axes[0].set_title('Huber Loss over Epochs')
    axes[0].set_xlabel('Epochs')
    axes[0].legend()
    
    # Scatter Plot (Predicted vs Actual)
    axes[1].scatter(all_targets, all_preds, alpha=0.5, color='teal')
    axes[1].plot([all_targets.min(), all_targets.max()], 
                 [all_targets.min(), all_targets.max()], 'r--')
    axes[1].set_title('Actual vs Predicted Monthly Yield')
    axes[1].set_xlabel('Actual Yield (kWh/kWp)')
    axes[1].set_ylabel('Predicted Yield (kWh/kWp)')
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    train_model()
