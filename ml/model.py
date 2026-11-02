# ml/model.py — small CNN, ~70k parameters, input (batch, 1, 49, 40)
import torch, torch.nn as nn

def block(cin, cout):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(),
                         nn.Conv2d(cout, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(),
                         nn.MaxPool2d(2))

class KWS(nn.Module):
    def __init__(self, n_classes=12):
        super().__init__()
        self.f = nn.Sequential(block(1, 32), block(32, 64), block(64, 64))
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(0.3),
                                  nn.Linear(64, n_classes))
    def forward(self, x):
        return self.head(self.f(x))
