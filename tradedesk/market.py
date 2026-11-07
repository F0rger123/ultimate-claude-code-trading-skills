"""Market: base 5-minute bars plus higher timeframes, with a map from each base bar to the
last higher-timeframe bar that was already closed when that base bar closed (no look-ahead)."""
from . import data as D


class Frame:
    def __init__(self, bars, gran):
        self.gran = gran
        self.bars = bars
        self.t = [b[0] for b in bars]
        self.o = [b[1] for b in bars]
        self.h = [b[2] for b in bars]
        self.l = [b[3] for b in bars]
        self.c = [b[4] for b in bars]
        self.v = [b[5] for b in bars]
        self.cache = {}

    def __len__(self):
        return len(self.bars)

    def memo(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]


class Market:
    def __init__(self, bars, symbol="BTC", base=300):
        self.symbol = symbol
        self.base = base
        self.b = Frame(bars, base)
        self.frames = {base: self.b}
        self.maps = {base: list(range(len(bars)))}

    def frame(self, gran):
        if gran not in self.frames:
            f = Frame(D.resample(self.b.bars, gran), gran)
            m = []
            j = -1
            for t in self.b.t:
                close = t + self.base
                while j + 1 < len(f.t) and f.t[j + 1] + gran <= close:
                    j += 1
                m.append(j)
            self.frames[gran] = f
            self.maps[gran] = m
        return self.frames[gran]

    def at(self, gran, arr, i):
        """Value of a higher-timeframe series as known at the close of base bar i."""
        j = self.maps[gran][i]
        return arr[j] if j >= 0 else None

    def closes_tf(self, gran, i):
        """True when base bar i is the last base bar of a gran bucket (the gran bar just closed)."""
        return (self.b.t[i] + self.base) % gran == 0

    def slice(self, start_t, end_t):
        return Market([b for b in self.b.bars if start_t <= b[0] < end_t], self.symbol, self.base)
