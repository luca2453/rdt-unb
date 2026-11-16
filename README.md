# RDT-UnB — Transferência confiável sobre UDP

Trabalho final de **CIC0236 – Teleinformática e Redes 2** (UnB, 2026/2), grupo 12.

Cliente do protocolo RDT-UnB com três modos de transferência confiável sobre UDP:

| Protocolo | `--protocol` | Janela (`--window-size`) |
|---|---|---|
| Stop-and-Wait | `saw` | 1 |
| Go-Back-N | `gbn` | 4, 8 ou 16 |
| Selective Repeat | `sr` | 4, 8 ou 16 |

## Estrutura

```
client.py               cliente (SAW, GBN e SR)
rdt_diagnostico.py      teste rápido do servidor
graficos.py             RTT (com linha do RTO) e throughput instantâneo
graficos_comparacao.py  gráfico GBN x SR
Makefile                atalhos para rodar os protocolos
docs/                   relatórios (LaTeX)
metricas/               CSVs, BINs e PNGs gerados (criada na execução)
```

## Instalação

Requer Python 3.10+. O `client.py` usa só a biblioteca padrão; o `matplotlib` é usado nos gráficos.

```bash
sudo apt install -y python3-venv     # só se o venv der erro (Ubuntu/WSL)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No Windows (PowerShell): `python -m venv .venv` e `.\.venv\Scripts\Activate.ps1`.

## Uso

```bash
python rdt_diagnostico.py   # testa o servidor

# Stop-and-Wait (sem timeout adaptativo: janela 1, timeout fixo de 500 ms)
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol saw --window-size 1

# GBN com janela 16 e timeout fixo de 500 ms (padrão)
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol gbn --window-size 16

# SR com janela 16, timeout adaptativo e 5% de perda simulada
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol sr --window-size 16 \
    --timeout adaptive --drop-chance 0.05

# SR adaptativo ajustando o estimador (padrões do TCP) e o piso de RTO
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol sr --window-size 16 \
    --timeout adaptive --alpha 0.125 --beta 0.25 --min-rto 100
```

Por padrão o cliente roda com `--timeout fixed` (500 ms). Use `--timeout adaptive` para ativar o estimador EWMA (detalhes na seção abaixo). SAW ignora `--timeout`: é sempre fixo.

| Argumento | Obrigatório | Descrição |
|---|---|---|
| `--server` | sim | IP do servidor (porta 8080/UDP) |
| `--group` | sim | grupo enviado no `HELLO` |
| `--file` | sim | `small`, `medium` ou `large` |
| `--protocol` | não | `saw` (padrão), `gbn` ou `sr` |
| `--window-size` | não | 1, 4, 8 ou 16 |
| `--drop-chance` | não | perda simulada (ex.: `0.1` = 10%) |
| `--timeout` | não | `fixed` (padrão, 500 ms) ou `adaptive` |
| `--alpha` | não | peso do EWMA do RTT estimado (padrão TCP: 0.125) |
| `--beta` | não | peso do EWMA do DevRTT (padrão TCP: 0.25) |
| `--min-rto` | não | piso do RTO adaptativo em ms (padrão: 100, RFC 6298) |

Ao final o cliente valida o MD5 e gera, dentro da pasta `metricas/`:

- `metrics_<grupo>_<protocolo><janela>_<fixo|adaptativo>_drop<%>_<data>.csv` (ex.: `metrics_grupo12_sr16_fixo_drop10_...csv`; SAW fica `saw`, pois usa janela 1) — uma linha por segmento (`segment, timestamp, size_bytes, rtt_ms, rtt_estimated_ms, timeout_ms, throughput_kbps, retransmissions, timeout_occurred, window_size, protocol, simulated_loss`);
- `recebido_<grupo>_<arquivo>.bin` — o arquivo recebido;
- `metrics_...png` — gráfico de RTT e throughput do CSV, gerado automaticamente (requer `matplotlib`).

### Perda simulada

Com `--drop-chance P`, o cliente descarta cada `DATA` recebido com probabilidade P (seed fixa 12345) e não envia o `ACK`; o segmento é recuperado pelo timeout. A coluna `simulated_loss` conta os descartes de cada segmento.

### Timeout adaptativo

Com `--timeout adaptive`, o timeout de cada segmento é `RTT_est + 4×DevRTT` calculado por EWMA (Karn's algorithm: segmentos retransmitidos não alimentam o estimador). A cada timeout real, o RTO dobra (backoff da RFC 6298), limitado ao teto de 1000 ms, e volta a descer após a próxima amostra válida. `--min-rto` define o piso.

### Gráficos

```bash
python graficos.py metricas/metrics_grupo12_saw_....csv
python graficos_comparacao.py metricas/metrics_grupo12_gbn_....csv metricas/metrics_grupo12_sr_....csv metricas/comparacao.png
```

O gráfico de cada run tem dois painéis:

- **RTT (painel de cima)** com a linha do RTO sobreposta. No timeout fixo a linha do RTO é omitida; no adaptativo o painel passa a escala log quando o RTO fica uma década acima do RTT (ex.: piso de 100 ms com RTT de ~33 ms).
- **Throughput instantâneo (painel de baixo)**: média móvel de 3 s (janela deslizante de tempo sobre os timestamps do CSV), a mesma grandeza do medido/teórico do relatório, com linhas de referência para ambos.

### Atalhos (Linux/WSL)

```bash
make test        # testa o servidor
make saw         # Stop-and-Wait (sempre timeout fixo)
make gbn16       # GBN, janela 16, timeout FIXO (padrão do Makefile)
make sr16        # SR, janela 16, timeout FIXO (padrão do Makefile)
make sr16 TIMEOUT=adaptive DROP_CHANCE=0.05    # SR adaptativo com 5% de perda
make sr16 TIMEOUT=fixed DROP_CHANCE=0.10       # SR fixo com 10% de perda
make graph CSV=metricas/metrics_....csv   # regenera o gráfico de um CSV
make check       # confere a sintaxe dos .py
make clean       # remove metricas/ e caches
```

Variáveis do Makefile: `SERVER`, `GROUP`, `FILE`, `WINDOW`, `DROP_CHANCE`, `TIMEOUT` (`fixed`/`adaptive`), `MIN_RTO`, `ALPHA`, `BETA`.

## Autores

- Enzo Morrone de Azevedo Muniz
- Luca Valderramos Cirino
- Raul Myron Silva Amorim
