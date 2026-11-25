"""
PPG analysis for MAX30102 raw logs.

Usage:
  python analyze.py subject01.csv                      # analyze + interactive viewer
  python analyze.py subject01.csv --window 15          # 15 s scroll window
  python analyze.py subject01.csv --start 30 --end 120 # only analyze 30 s - 120 s
  python analyze.py subject01.csv --no-show            # save PNGs only (no window)
"""
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator
from matplotlib.widgets import Slider
from scipy.signal import butter, filtfilt, find_peaks

FS = 200.0  # must match SAMPLE_RATE in the firmware


# ---------- time-axis helpers ----------
def fmt_time(x, _pos=None):
    """Seconds -> mm:ss or h:mm:ss tick labels."""
    x = max(x, 0)
    h, rem = divmod(int(round(x)), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def set_time_axis(ax, span_s):
    """Choose sensible tick spacing for the visible span."""
    steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600]
    target = span_s / 8
    major = next((s for s in steps if s >= target), steps[-1])
    ax.xaxis.set_major_locator(MultipleLocator(major))
    ax.xaxis.set_minor_locator(MultipleLocator(major / 5 if major >= 5 else major / 2))
    ax.xaxis.set_major_formatter(FuncFormatter(fmt_time))
    ax.grid(which="major", alpha=0.35)
    ax.grid(which="minor", alpha=0.12)


# ---------- load + QC ----------
def load(path, start, end):
    df = pd.read_csv(path)
    gaps = int((df.idx.diff().dropna() != 1).sum())
    t_sensor = df.idx.values / FS
    host = df.host_time.values
    print(f"Samples: {len(df)}   index gaps: {gaps}")
    print(f"Sensor time {len(df)/FS:.1f}s  vs  host time {host[-1]-host[0]:.1f}s")

    t = t_sensor - t_sensor[0]
    m = np.ones(len(df), bool)
    if start is not None: m &= t >= start
    if end is not None:   m &= t <= end
    df, t = df[m], t[m]
    ir = df.ir.values.astype(float)
    if ir.max() >= 262143: print("WARNING: IR saturated, lower LED brightness")
    if ir.mean() < 20000:  print("WARNING: low IR, finger missing or LED too dim")
    return t, ir


# ---------- processing ----------
def process(ir):
    b, a = butter(2, [0.5, 5.0], btype="band", fs=FS)
    ppg = -filtfilt(b, a, ir)              # invert: more blood = less reflected light
    ppg = (ppg - np.mean(ppg)) / np.std(ppg)

    peaks, _ = find_peaks(ppg, distance=int(0.3 * FS), prominence=0.5)
    ibi = np.diff(peaks) / FS * 1000.0     # ms
    t_ibi = peaks[1:] / FS                 # time of the beat ending each interval

    med = pd.Series(ibi).rolling(5, center=True, min_periods=1).median().values
    valid = np.abs(ibi - med) < 0.2 * med
    return ppg, peaks, ibi, t_ibi, valid


def summarize(ibi, valid, n_peaks):
    x = ibi[valid]
    print(f"Beats: {n_peaks}  used: {valid.sum()}  rejected: {(~valid).sum()}")
    print(f"Mean HR: {60000/x.mean():.1f} bpm   SDNN: {x.std(ddof=1):.1f} ms   "
          f"RMSSD: {np.sqrt(np.mean(np.diff(x)**2)):.1f} ms   (PRV, not ECG-HRV)")


# ---------- plotting ----------
def overview_figure(t, ppg, peaks, ibi, t_ibi, valid):
    dur = t[-1] - t[0]
    step = max(1, int(FS / 50))  # signal is band-limited to 5 Hz, 50 Hz display is plenty
    hr = 60000.0 / ibi
    hr_smooth = pd.Series(np.where(valid, hr, np.nan)).rolling(10, center=True, min_periods=3).mean()

    fig, axs = plt.subplots(3, 1, figsize=(14, 8), sharex=True,
                            gridspec_kw={"height_ratios": [2, 1.3, 1.3]})
    axs[0].plot(t[::step], ppg[::step], lw=0.6, color="tab:blue")
    axs[0].set_ylabel("PPG (a.u.)"); axs[0].set_title("Overview")

    axs[1].plot(t_ibi[valid], hr[valid], ".", ms=3, color="tab:gray", alpha=0.6, label="beat-to-beat")
    axs[1].plot(t_ibi, hr_smooth, lw=1.8, color="tab:red", label="smoothed")
    axs[1].set_ylabel("HR (bpm)"); axs[1].legend(loc="upper right", ncol=2, fontsize=8)

    axs[2].plot(t_ibi[valid], ibi[valid], ".-", ms=3, lw=0.6, color="tab:green")
    if (~valid).any():
        axs[2].plot(t_ibi[~valid], ibi[~valid], "rx", ms=5, label="rejected")
        axs[2].legend(loc="upper right", fontsize=8)
    axs[2].set_ylabel("IBI (ms)"); axs[2].set_xlabel("Time (mm:ss)")

    set_time_axis(axs[2], dur)
    for ax in axs[:2]: set_time_axis(ax, dur)
    axs[2].set_xlim(t[0], t[-1])
    fig.tight_layout()
    return fig


def zoom_figure(t, ppg, peaks, window, save_prefix=None, show=True):
    """Scrollable zoom window with a slider."""
    t0, t1 = t[0], t[-1]
    window = min(window, t1 - t0)
    fig, ax = plt.subplots(figsize=(14, 4.5))
    plt.subplots_adjust(bottom=0.22)
    ax.plot(t, ppg, lw=1.0, color="tab:blue")
    ax.plot(t[peaks], ppg[peaks], "rv", ms=6)
    ax.set_ylabel("PPG (a.u.)"); ax.set_xlabel("Time (mm:ss)")
    ax.set_title(f"Zoom view ({window:.0f} s window): drag the slider")
    ax.set_ylim(ppg.min() * 1.05, ppg.max() * 1.05)

    def apply(start):
        ax.set_xlim(start, start + window)
        set_time_axis(ax, window)
        fig.canvas.draw_idle()

    apply(t0)
    if t1 - t0 > window:
        sax = plt.axes([0.12, 0.06, 0.76, 0.04])
        sl = Slider(sax, "Start (s)", t0, t1 - window, valinit=t0)
        sl.on_changed(apply)
        fig._slider = sl  # keep reference
    return fig


def save_snapshots(t, ppg, peaks, window, prefix):
    """Save zoom PNGs at start / middle / end of the recording."""
    dur = t[-1] - t[0]
    window = min(window, dur)
    for label, s in [("start", t[0]), ("middle", t[0] + (dur - window) / 2), ("end", t[-1] - window)]:
        fig, ax = plt.subplots(figsize=(14, 4))
        m = (t >= s) & (t <= s + window)
        ax.plot(t[m], ppg[m], lw=1.0)
        pk = peaks[(t[peaks] >= s) & (t[peaks] <= s + window)]
        ax.plot(t[pk], ppg[pk], "rv", ms=6)
        ax.set_xlim(s, s + window); set_time_axis(ax, window)
        ax.set_xlabel("Time (mm:ss)"); ax.set_ylabel("PPG (a.u.)"); ax.set_title(f"{label} segment")
        fig.tight_layout(); fig.savefig(f"{prefix}_zoom_{label}.png", dpi=150); plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--window", type=float, default=10.0, help="zoom window length in seconds")
    p.add_argument("--start", type=float, help="analyze from this time (s)")
    p.add_argument("--end", type=float, help="analyze up to this time (s)")
    p.add_argument("--no-show", action="store_true", help="save PNGs without opening windows")
    args = p.parse_args()

    t, ir = load(args.csv, args.start, args.end)
    ppg, peaks, ibi, t_ibi, valid = process(ir)
    summarize(ibi, valid, len(peaks))

    prefix = args.csv.rsplit(".", 1)[0]
    f1 = overview_figure(t, ppg, peaks, ibi, t_ibi, valid)
    f1.savefig(f"{prefix}_overview.png", dpi=150)
    save_snapshots(t, ppg, peaks, args.window, prefix)
    print(f"Saved {prefix}_overview.png and {prefix}_zoom_*.png")

    if not args.no_show:
        f2 = zoom_figure(t, ppg, peaks, args.window)
        plt.show()


if __name__ == "__main__":
    main()
