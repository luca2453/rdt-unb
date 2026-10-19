# Gera gráficos de RTT e throughput por segmento e o resumo teórico x medido.
# Uso: python graficos.py metricas_grupo12_small.csv [metricas_..._medium.csv ...]
import csv
import sys
import matplotlib.pyplot as plt

def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))

print(f"{'arquivo':40s} {'seg':>5s} {'RTT_med(ms)':>11s} {'teor(kbps)':>11s} {'med(kbps)':>10s} {'retx':>5s}")
for caminho in sys.argv[1:]:
    linhas = ler(caminho)
    seq = [int(l["seq"]) for l in linhas]
    rtt = [float(l["rtt_ms"]) for l in linhas]
    thr = [float(l["throughput_kbps"]) for l in linhas]
    bytes_tot = sum(int(l["payload_bytes"]) for l in linhas)
    seg_size = max(int(l["payload_bytes"]) for l in linhas)
    rtt_med = sum(rtt) / len(rtt)
    teorico = seg_size * 8 / rtt_med  # kbps (bits/ms)
    tempo_total_ms = float(linhas[-1]["t_fim_s"]) * 1000
    medido = bytes_tot * 8 / tempo_total_ms  # kbps: arquivo inteiro / tempo total (inclui timeouts e ACKs)
    retx = sum(int(l["retransmissoes"]) for l in linhas)
    print(f"{caminho:40s} {seg_size:5d} {rtt_med:11.2f} {teorico:11.2f} {medido:10.2f} {retx:5d}")

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    a1.plot(seq, rtt, lw=0.7)
    a1.axhline(rtt_med, ls="--", color="gray", label=f"média {rtt_med:.1f} ms")
    a1.set_ylabel("RTT (ms)"); a1.legend(); a1.grid(alpha=.3)
    a2.plot(seq, thr, lw=0.7, color="tab:orange")
    a2.axhline(teorico, ls="--", color="gray", label=f"teórico {teorico:.0f} kbps")
    a2.set_ylabel("Throughput (kbps)"); a2.set_xlabel("Segmento (seq)")
    a2.legend(); a2.grid(alpha=.3)
    fig.suptitle(caminho.replace(".csv", ""))
    fig.tight_layout()
    saida = caminho.replace(".csv", ".png")
    fig.savefig(saida, dpi=150)
    print(f"   -> {saida}")
