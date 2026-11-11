# Compara GBN e SR (mesma janela, mesmo cenário de perda) segmento a segmento.
# Uso: python graficos_comparacao.py <csv_gbn> <csv_sr> [saida.png]
#
# Painel 1: throughput efetivo acumulado ao longo dos segmentos
#           (bytes entregues em ordem até o segmento i / tempo decorrido até ele)
# Painel 2: retransmissões acumuladas ao longo dos segmentos
# Também imprime, para a questão (b), quantos segmentos cada protocolo
# retransmitiu por perda simulada.
import csv
import sys
from datetime import datetime

import matplotlib.pyplot as plt


def carregar(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = sorted(csv.DictReader(f), key=lambda r: int(r["segment"]))
    t = [datetime.fromisoformat(r["timestamp"]).timestamp() for r in linhas]
    t0 = min(t) - float(linhas[0]["rtt_ms"]) / 1000  # instante do 1o REQ
    seg, thr, retx_acum = [], [], []
    bytes_ok, retx, t_max = 0, 0, t0
    for r, ti in zip(linhas, t):
        bytes_ok += int(r["size_bytes"])
        retx += int(r["retransmissions"])
        t_max = max(t_max, ti)  # prefixo 0..i só está completo no maior instante
        seg.append(int(r["segment"]))
        thr.append(bytes_ok * 8 / 1000 / max(t_max - t0, 1e-6))  # kbps
        retx_acum.append(retx)
    perdas = sum(int(r.get("simulated_loss", 0) or 0) for r in linhas)
    proto = linhas[0]["protocol"].upper()
    janela = linhas[0]["window_size"]
    return proto, janela, seg, thr, retx_acum, retx, perdas


def main():
    if len(sys.argv) < 3:
        sys.exit("uso: python graficos_comparacao.py <csv_gbn> <csv_sr> [saida.png]")
    saida = sys.argv[3] if len(sys.argv) > 3 else "comparacao_gbn_sr.png"
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    print(f"{'protocolo':10s} {'janela':>6s} {'perdas_sim':>10s} {'retx':>6s} {'retx/perda':>10s}")
    for caminho, cor in zip(sys.argv[1:3], ["tab:red", "tab:blue"]):
        proto, janela, seg, thr, retx_acum, retx, perdas = carregar(caminho)
        rotulo = f"{proto}-{janela}"
        # ignora os primeiros segmentos, em que o tempo decorrido ainda é ~0
        k = min(int(janela) * 2, len(seg) - 1)
        a1.plot(seg[k:], thr[k:], color=cor, lw=1.2, label=rotulo)
        a2.plot(seg, retx_acum, color=cor, lw=1.2, label=rotulo)
        razao = retx / perdas if perdas else float("nan")
        print(f"{proto:10s} {janela:>6s} {perdas:10d} {retx:6d} {razao:10.2f}")
    a1.set_ylabel("Throughput acumulado (kbps)")
    a1.grid(alpha=.3); a1.legend()
    a2.set_ylabel("Retransmissões acumuladas")
    a2.set_xlabel("Segmento (seq)")
    a2.grid(alpha=.3); a2.legend()
    fig.tight_layout()
    fig.savefig(saida, dpi=150)
    print(f"-> {saida}")


if __name__ == "__main__":
    main()
