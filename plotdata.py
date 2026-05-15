import re
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import os
import glob



def find_newest_log():
    files = glob.glob("logs/rawdatalog*.txt")
    newest = max(files, key=os.path.getmtime)

    print("Newest log:", newest)
    return newest
def parse_log_file(path):
    rows = []

    with open(path, "r") as f:
        for line in f:
            if line.startswith("---"):
                continue

            pairs = re.findall(r"(\w+):([-\d\.]+)", line)
            if not pairs:
                continue

            row = {}
            for key, value in pairs:
                try:
                    row[key] = float(value)
                except ValueError:
                    pass

            rows.append(row)

    return pd.DataFrame(rows)


def plot_variables_subplots(df, variables, last_n=None):
    if last_n is not None and last_n > 0:
        df = df.tail(last_n)

    x = df.index
    num_plots = len(variables)

    fig, axes = plt.subplots(num_plots, 1, figsize=(10, 3 * num_plots), sharex=True)
    if num_plots == 1:
        axes = [axes]

    for ax, var in zip(axes, variables):
        if var not in df.columns:
            print(f"[WARNING] Variable '{var}' not found in log file.")
            continue

        ax.plot(x, df[var])
        ax.set_ylabel(var)
        ax.set_title(var)
        ax.grid(True)

    axes[-1].set_xlabel("Sample Index")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    find_newest_log()
    parser = argparse.ArgumentParser(description="Plot log file data.")

    parser.add_argument("--file", "-f", type=str,
                        default=find_newest_log(),
                        help="Path to log file")

    parser.add_argument("--last", "-l", type=int, default=None,
                        help="Number of last lines to plot")

    parser.add_argument("--vars", "-v", nargs="+", type=str,
                        default=["Pfc", "Vbat", "Iout", "Pout", "Tfc"],
                        help="Variables to plot (space-separated)")

    args = parser.parse_args()

    df = parse_log_file(args.file)
    plot_variables_subplots(df, args.vars, last_n=args.last)
