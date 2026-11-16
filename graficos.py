# Gera gráficos de RTT e throughput instantâneo (média móvel) e o resumo teórico x medido.
# Uso: python graficos.py metricas/metrics_grupo12_saw_20261026_012200.csv [...]
# O PNG é salvo na mesma pasta do CSV.
import csv
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

    # Throughput agregado com média móvel: bytes entregues numa janela
    # deslizante de TEMPO (W_TIME_S) divididos pela duração dela — a mesma
    # grandeza do medido/teórico do relatório (com a janela em voo).
    # SR entrega fora de ordem, então o timestamp não é monotônico na ordem
    # do CSV; monotizamos (te) para que a janela deslizante faça sentido.
    W_TIME_S = 3.0      # janela deslizante de tempo (s)
    DT_MINIMO_S = 0.05  # piso do dt: evita explosão em rajadas no mesmo ms
    te: list[float] = []
    ultimo_t = float("-inf")
    for ti in t:
        ultimo_t = max(ultimo_t, ti)
        te.append(ultimo_t)
    prefixo = [0]
    for size in sizes:
        prefixo.append(prefixo[-1] + size)
    inst = []
    j = 0
    for i in range(len(sizes)):
        while te[i] - te[j] > W_TIME_S:
            j += 1
        bytes_janela = prefixo[i + 1] - prefixo[j]
        dt = max(te[i] - te[j], DT_MINIMO_S)
        inst.append(bytes_janela * 8 / 1000 / dt)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    a1.plot(seg, rtt, lw=0.7)
    # Linha do RTO ao longo da transferência: só faz sentido junto ao RTT
    # quando é da mesma ordem de grandeza (modo adaptativo); com timeout
    # fixo (500 ms) ela distorceria a escala do painel.

    # Plota quando o RTO é da escala do RTT (adaptativo sem spikes) ou quando
    # ele varia (adaptativo com backoff: os picos até o teto são justamente o
    # que se quer ver). Só omite no timeout fixo (constante em 500 ms).
    if min(tmo) != max(tmo) or max(tmo) < 10 * rtt_med:
        teto = max(max(rtt), rtt_med) * 1.5
        a1.plot(seg, tmo, lw=1.0, color="tab:red",
                label=f"timeout adaptativo ({min(tmo):.0f}–{max(tmo):.0f} ms)")
        if max(tmo) > teto:
            # RTO estruturalmente acima da escala do RTT (ex.: piso de RTO de
            # 100 ms com RTT de ~30 ms): em linear ele viraria uma constante
            # no teto, então escala log mostra RTT e RTO com posições reais.
            a1.set_yscale("log")
            a1.set_ylim(min(min(rtt), min(tmo)) * 0.7,
                        max(max(rtt), max(tmo)) * 1.3)
        else:
            a1.set_ylim(0, teto * 1.08)
    a1.axhline(rtt_med, ls="--", color="gray", label=f"média {rtt_med:.1f} ms")
    a1.set_ylabel("RTT (ms)"); a1.legend(); a1.grid(alpha=.3)
    # Oculta o transiente de aquecimento da média móvel (~4% iniciais):
    # no começo a janela de tempo ainda não está cheia e o denominador
    # exclui o RTT de setup, inflando artificialmente o instantâneo.
    aquecimento = max(1, int(0.04 * len(sizes)))
    a2.plot(seg[aquecimento:], inst[aquecimento:], lw=0.7, color="tab:orange")
    a2.set_ylabel("Throughput instantâneo (kbps)"); a2.set_xlabel("Segmento (seq)")
    # Eixo y com perspectiva mínima: sem ancorar no zero (a curva viraria uma
    # linha reta no topo), mas garantindo um intervalo de pelo menos ±20% do
    # nível do throughput, para variações pequenas não parecerem enormes.
    inst_vis = inst[aquecimento:]
    lo = min(min(inst_vis), medido, teorico)
    hi = max(max(inst_vis), medido, teorico)
    centro = (lo + hi) / 2
    meia_faixa = max((hi - lo) / 2, 0.2 * max(teorico, medido))
    a2.set_ylim(max(0, centro - 1.15 * meia_faixa), centro + 1.15 * meia_faixa)
    a2.axhline(medido, ls="--", color="tab:green", label=f"medido {medido:.1f} kbps")
    a2.axhline(teorico, ls="--", color="gray", label=f"teórico {teorico:.0f} kbps")
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
