import glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9
})

def calculate_unavailability(df, kill_time):
    post_kill_success = df[(df['t_sent'] >= kill_time) & (df['status'] == 'SUCCESS')]
    if post_kill_success.empty:
        return np.nan
    t_first_recovered = post_kill_success['t_sent'].iloc[0]
    return t_first_recovered - kill_time

def generate_cdf():
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    
    colors = {
        ('etcd', 'aggressive'): '#0055ff',
        ('etcd', 'conservative'): '#001166',
        ('redis', 'aggressive'): '#ff3333',
        ('redis', 'conservative'): '#880000'
    }

    found_any = False
    for system in ['etcd', 'redis']:
        for mode in ['aggressive', 'conservative']:
            unavail_times = []
            files = sorted(glob.glob(f"results/{system}_{mode}_*.csv"))
            for f in files:
                meta_file = f.replace('.csv', '.meta')
                try:
                    with open(meta_file) as mf:
                        kill_time = float(mf.read().split(',')[0])
                    df = pd.read_csv(f)
                    unavail = calculate_unavailability(df, kill_time)
                    if not np.isnan(unavail):
                        unavail_times.append(unavail)
                except Exception:
                    continue

            if len(unavail_times) > 0:
                found_any = True
                unavail_times = np.sort(unavail_times)
                cdf = np.arange(1, len(unavail_times) + 1) / len(unavail_times)
                linestyle = '-' if system == 'etcd' else '--'
                label = f"{system.upper()} ({mode})"
                ax.step(unavail_times, cdf, label=label, linestyle=linestyle, 
                        color=colors.get((system, mode), 'black'), where='post', lw=1.8)

    if not found_any:
        print("No result CSV files found in results/ directory.")
        return

    ax.set_xlabel("Client-Visible Unavailability Delta t (seconds)")
    ax.set_ylabel("Empirical CDF P(X <= Delta t)")
    ax.set_title("Failover Unavailability Distribution Across Configurations (N >= 20)")
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(frameon=True, loc='lower right')
    
    plt.savefig("results/figure1_unavailability_cdf.pdf", bbox_inches='tight')
    plt.savefig("results/figure1_unavailability_cdf.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated results/figure1_unavailability_cdf.pdf and .png")

def generate_timeline():
    sample_files = sorted(glob.glob("results/etcd_aggressive_*.csv"))
    if not sample_files:
        print("No sample files found to generate timeline.")
        return
    sample_file = sample_files[0]
    meta_file = sample_file.replace('.csv', '.meta')
    with open(meta_file) as mf:
        kill_time = float(mf.read().split(',')[0])
    
    df = pd.read_csv(sample_file)
    df['rel_time'] = df['t_sent'] - kill_time
    df['time_bin'] = np.floor(df['rel_time'] / 0.1) * 0.1
    throughput = df[df['status'] == 'SUCCESS'].groupby('time_bin').size() / 0.1

    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.plot(throughput.index, throughput.values, color='#0066cc', lw=1.8, label='Write Throughput')
    ax.axvline(x=0, color='red', linestyle='--', lw=1.5, label='Leader SIGKILL')
    ax.set_xlim(-2.0, 5.0)
    ax.set_xlabel("Time Relative to Fault (seconds)")
    ax.set_ylabel("Throughput (Writes/sec)")
    ax.set_title("Write Throughput Dynamics Across Leader Failover (etcd aggressive)")
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper right')
    
    plt.savefig("results/figure2_throughput_timeline.pdf", bbox_inches='tight')
    plt.savefig("results/figure2_throughput_timeline.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated results/figure2_throughput_timeline.pdf and .png")

if __name__ == "__main__":
    generate_cdf()
    generate_timeline()
