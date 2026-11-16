# Gera gráficos de RTT e throughput por segmento e o resumo teórico x medido.
# Uso: python graficos.py metricas/metrics_grupo12_saw_20261026_012200.csv [...]
# O PNG é salvo na mesma pasta do CSV.
import csv
import statistics as st
import sys
from datetime import datetime

import matplotlib.pyplot as plt

def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def gerar(caminho):
    linhas = ler(caminho)
    seg = [int(l["segment"]) for l in linhas]
    rtt = [float(l["rtt_ms"]) for l in linhas]
    tmo = [float(l["timeout_ms"]) for l in linhas]
    sizes = [int(l["size_bytes"]) for l in linhas]
    bytes_tot = sum(sizes)
    seg_size = max(sizes)
    rtt_med = sum(rtt) / len(rtt)
    janela = int(linhas[0]["window_size"])
    teorico = janela * seg_size * 8 / rtt_med  # kbps (bits/ms)
    # Tempo real da transferência: instante do 1o REQ (primeiro timestamp
    # menos o RTT dele) até o último recebimento registrado no CSV.
    t = [datetime.fromisoformat(l["timestamp"]).timestamp() for l in linhas]
    tempo_total_ms = (max(t) - min(t)) * 1000 + rtt[0]
    medido = bytes_tot * 8 / tempo_total_ms  # kbps: bits/ms
    retx = sum(int(l["retransmissions"]) for l in linhas)
    print(f"{'arquivo':40s} {'seg':>5s} {'RTT_med(ms)':>11s} {'teor(kbps)':>11s} {'med(kbps)':>10s} {'retx':>5s}")
    print(f"{caminho:40s} {seg_size:5d} {rtt_med:11.2f} {teorico:11.2f} {medido:10.2f} {retx:5d}")

    # Throughput segmento a segmento (coluna do CSV: size_bytes*8/rtt_ms).
    # Sem média móvel: cada ponto é o throughput do próprio segmento, então
    # eventos pontuais (pico de RTT, timeout) aparecem e desaparecem junto
    # com o segmento em que ocorreram, sem contaminar os vizinhos.
    inst = [float(l["throughput_kbps"]) for l in linhas]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    a1.plot(seg, rtt, lw=0.7)
    # Linha do RTO ao longo da transferência: só faz sentido junto ao RTT
    # quando é da mesma ordem de grandeza (modo adaptativo); com timeout
    # fixo (500 ms) ela distorceria a escala do painel.
    if max(tmo) < 10 * rtt_med:
        a1.plot(seg, tmo, lw=1.0, color="tab:red",
                label=f"timeout adaptativo ({min(tmo):.0f}–{max(tmo):.0f} ms)")
    a1.axhline(rtt_med, ls="--", color="gray", label=f"média {rtt_med:.1f} ms")
    a1.set_ylabel("RTT (ms)"); a1.legend(); a1.grid(alpha=.3)
    a2.plot(seg, inst, lw=0.7, color="tab:orange")
    a2.set_ylabel("Throughput por segmento (kbps)"); a2.set_xlabel("Segmento (seq)")
    # Escala pelo throughput POR SEGMENTO (size*8/rtt ≈ seg_size*8/RTT); o
    # agregado (com a janela em voo) é outra ordem de grandeza, então as
    # linhas de referência agregadas só entram se caírem na escala do eixo.
    lo = min(inst)
    hi = max(inst)
    centro = (lo + hi) / 2
    meia_faixa = max((hi - lo) / 2, 0.2 * st.median(inst))
    a2.set_ylim(max(0, centro - 1.15 * meia_faixa), centro + 1.15 * meia_faixa)
    if a2.get_ylim()[0] <= medido <= a2.get_ylim()[1]:
        a2.axhline(medido, ls="--", color="tab:green", label=f"medido {medido:.1f} kbps")
    if a2.get_ylim()[0] <= teorico <= a2.get_ylim()[1]:
        a2.axhline(teorico, ls="--", color="gray", label=f"teórico {teorico:.0f} kbps")
    if a2.get_legend_handles_labels()[0]:
        a2.legend()
    a2.grid(alpha=.3)
    fig.suptitle(caminho.replace(".csv", ""))
    fig.tight_layout()
    saida = caminho.replace(".csv", ".png")
    fig.savefig(saida, dpi=150)
    print(f"   -> {saida}")
    return saida

if __name__ == "__main__":
    for caminho in sys.argv[1:]:
        gerar(caminho)
