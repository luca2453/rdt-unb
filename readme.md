# RDT-UnB — Transferência confiável sobre UDP

Trabalho final de **CIC0236 – Teleinformática e Redes 2** (UnB, 2026/2), grupo 12.

Cliente para o protocolo RDT-UnB com três modos de transferência confiável sobre UDP:

| Protocolo | `--protocol` | Janela (`--window-size`) |
|---|---|---|
| Stop-and-Wait | `saw` | 1 |
| Go-Back-N | `gbn` | 4, 8 ou 16 |
| Selective Repeat | `sv` | 4, 8 ou 16 |

## Estrutura

```
client.py               cliente (SAW, GBN e SR)
rdt_diagnostico.py      teste rápido do servidor (PING, HELLO, REQ/DATA)
graficos.py             gráficos de RTT e throughput por segmento
graficos_comparacao.py  gráfico GBN x SR (throughput e retransmissões acumuladas)
Makefile                atalhos para rodar os protocolos
docs/                   relatórios (LaTeX)
```

## Instalação

Requer **Python 3.10+**. O `client.py` usa apenas a biblioteca padrão; o
`matplotlib` só é necessário para os gráficos.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se o PowerShell bloquear o `Activate.ps1`, libere scripts só para a sessão atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Com a venv ativa, o terminal mostra `(.venv)` no início da linha. Para sair: `deactivate`.

## Uso

### 1. Testar o servidor

```bash
python rdt_diagnostico.py
```

Deve terminar com `Servidor operacional.`

### 2. Rodar uma transferência

```bash
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol saw --window-size 1
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol gbn --window-size 16
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol sv  --window-size 16
```

| Argumento | Obrigatório | Descrição |
|---|---|---|
| `--server` | sim | IP do servidor RDT-UnB (porta 8080) |
| `--group` | sim | identificador do grupo, enviado no `HELLO` |
| `--file` | sim | `small`, `medium` ou `large` |
| `--protocol` | não | `saw` (padrão), `gbn` ou `sv` |
| `--window-size` | não | 1, 4, 8 ou 16 |
| `--drop-chance` | não | probabilidade de perda simulada (ex.: `0.1` = 10%); padrão `0` |

Sem `--group` o cliente não roda.

Ao final, o cliente compara o MD5 calculado com o informado pelo servidor e gera:

- `metrics_<grupo>_<protocolo>_<data>.csv`: uma linha por segmento, com
  `segment, timestamp, size_bytes, rtt_ms, rtt_estimated_ms, timeout_ms,
  throughput_kbps, retransmissions, timeout_occurred, window_size, protocol,
  simulated_loss`;
- `recebido_<grupo>_<arquivo>.bin`: o arquivo recebido.

### 3. Simular perda

```bash
python client.py --server 137.131.178.229 --group grupo12 --file small --protocol gbn --window-size 16 --drop-chance 0.1
```

O cliente descarta cada `DATA` recebido com probabilidade `P` (seed fixa 12345)
e não envia o `ACK`; o segmento é recuperado pelo timeout do protocolo. A coluna
`simulated_loss` do CSV indica quantas vezes o `DATA` daquele segmento foi
descartado de propósito.

### 4. Gerar os gráficos

```bash
# RTT e throughput por segmento (um ou mais CSVs)
python graficos.py metrics_grupo12_saw_AAAAMMDD_HHMMSS.csv

# GBN x SR com a mesma janela e o mesmo cenário de perda
python graficos_comparacao.py metrics_grupo12_gbn_....csv metrics_grupo12_sv_....csv comparacao.png
```

O `graficos_comparacao.py` também imprime quantas retransmissões cada protocolo
fez por perda simulada.

### Atalhos com `make` (Linux/macOS)

```bash
make saw
make gbn16
make sr16
make gbn16 DROP_CHANCE=0.1
make test
```

Variáveis: `SERVER`, `GROUP`, `FILE`, `WINDOW`, `DROP_CHANCE`.

## Autores

- Enzo Morrone de Azevedo Muniz
- Luca Valderramos Cirino
- Raul Myron Silva Amorim