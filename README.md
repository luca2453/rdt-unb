# RDT-UnB — Transferência confiável sobre UDP

Trabalho final de **CIC0236 – Teleinformática e Redes 2** (UnB, 2026/2), grupo 12.

Cliente do protocolo RDT-UnB com três modos de transferência confiável sobre UDP:

| Protocolo | `--protocol` | Janela (`--window-size`) |
|---|---|---|
| Stop-and-Wait | `saw` | 1 |
| Go-Back-N | `gbn` | 4, 8 ou 16 |
| Selective Repeat | `sv` | 4, 8 ou 16 |

## Estrutura

```
client.py               cliente (SAW, GBN e SR)
rdt_diagnostico.py      teste rápido do servidor
graficos.py             RTT e throughput por segmento
graficos_comparacao.py  gráfico GBN x SR
Makefile                atalhos para rodar os protocolos
docs/                   relatórios (LaTeX)
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

python client.py --server 137.131.178.229 --group grupo12 --file small --protocol saw --window-size 1
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol gbn --window-size 16
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol sv  --window-size 16
```

| Argumento | Obrigatório | Descrição |
|---|---|---|
| `--server` | sim | IP do servidor (porta 8080/UDP) |
| `--group` | sim | grupo enviado no `HELLO` |
| `--file` | sim | `small`, `medium` ou `large` |
| `--protocol` | não | `saw` (padrão), `gbn` ou `sv` |
| `--window-size` | não | 1, 4, 8 ou 16 |
| `--drop-chance` | não | perda simulada (ex.: `0.1` = 10%) |

Ao final o cliente valida o MD5 e gera:

- `metrics_<grupo>_<protocolo>_<data>.csv` — uma linha por segmento (`segment, timestamp, size_bytes, rtt_ms, rtt_estimated_ms, timeout_ms, throughput_kbps, retransmissions, timeout_occurred, window_size, protocol, simulated_loss`);
- `recebido_<grupo>_<arquivo>.bin` — o arquivo recebido.

### Perda simulada

Com `--drop-chance P`, o cliente descarta cada `DATA` recebido com probabilidade P (seed fixa 12345) e não envia o `ACK`; o segmento é recuperado pelo timeout. A coluna `simulated_loss` conta os descartes de cada segmento.

### Gráficos

```bash
python graficos.py metrics_grupo12_saw_....csv
python graficos_comparacao.py metrics_grupo12_gbn_....csv metrics_grupo12_sv_....csv comparacao.png
```

### Atalhos (Linux/WSL)

```bash
make test
make saw
make gbn16
make sr16
make gbn16 DROP_CHANCE=0.1
```

## Autores

- Enzo Morrone de Azevedo Muniz
- Luca Valderramos Cirino
- Raul Myron Silva Amorim
