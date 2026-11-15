PYTHON ?= python3
SERVER ?= 137.131.178.229
GROUP ?= grupo12
FILE ?= small
WINDOW ?= 4
DROP_CHANCE ?= 0
TIMEOUT ?= fixed
ALPHA ?= 0.125
BETA ?= 0.25
CSV ?=

.PHONY: all help run saw gbn gbn4 gbn8 gbn16 test check syntax graph clean

all: help

help:
	@echo "Comandos disponíveis:"
	@echo "  make saw       - executa Stop-and-Wait"
	@echo "  make gbn       - executa Go-Back-N (janela configurável)"
	@echo "  make gbn4      - executa Go-Back-N com janela 4"
	@echo "  make gbn8      - executa Go-Back-N com janela 8"
	@echo "  make gbn16     - executa Go-Back-N com janela 16"
	@echo "  make sr       - executa Selective Repeat (janela configurável)"
	@echo "  make sr4      - executa Selective Repeat com janela 4"
	@echo "  make sr8      - executa Selective Repeat com janela 8"
	@echo "  make sr16     - executa Selective Repeat com janela 16"
	@echo "  make test      - executa o teste básico do servidor"
	@echo "  make check     - verifica a sintaxe dos arquivos Python"
	@echo "  make graph CSV=metricas/metrics_...csv - gera gráficos do CSV"
	@echo "  make clean     - remove arquivos gerados (metricas/, PNGs, caches)"
	@echo ""
	@echo "Parâmetros: SERVER=$(SERVER) GROUP=$(GROUP) FILE=$(FILE) WINDOW=$(WINDOW)"
	@echo "            DROP_CHANCE=$(DROP_CHANCE) TIMEOUT=$(TIMEOUT) ALPHA=$(ALPHA) BETA=$(BETA)"

run: saw

saw:
	$(PYTHON) client.py --server $(SERVER) --group $(GROUP) --file $(FILE) --protocol saw --window-size 1 --drop-chance $(DROP_CHANCE)

gbn:
	$(PYTHON) client.py --server $(SERVER) --group $(GROUP) --file $(FILE) --protocol gbn --window-size $(WINDOW) --drop-chance $(DROP_CHANCE) --timeout $(TIMEOUT) --alpha $(ALPHA) --beta $(BETA)

gbn4:
	$(MAKE) gbn WINDOW=4

gbn8:
	$(MAKE) gbn WINDOW=8

gbn16:
	$(MAKE) gbn WINDOW=16

sr:
	$(PYTHON) client.py --server $(SERVER) --group $(GROUP) --file $(FILE) --protocol sr --window-size $(WINDOW) --drop-chance $(DROP_CHANCE) --timeout $(TIMEOUT) --alpha $(ALPHA) --beta $(BETA)

sr4:
	$(MAKE) sr WINDOW=4

sr8:
	$(MAKE) sr WINDOW=8

sr16:
	$(MAKE) sr WINDOW=16

test:
	$(PYTHON) rdt_diagnostico.py

syntax:
	$(PYTHON) -m py_compile client.py rdt_diagnostico.py graficos.py

check: syntax
	git diff --check

graph:
ifndef CSV
	$(error informe o CSV, por exemplo: make graph CSV=metricas/metrics_grupo12_saw_20261026_012200.csv)
endif
	$(PYTHON) graficos.py $(CSV)

clean:
	rm -f metricas/metrics_*.csv metricas/*.png metricas/recebido_*.bin
	rm -f metrics_*.csv metricas_*.csv metrics_*.png metricas_*.png comparacao*.png recebido_*.bin
	rm -rf __pycache__
	@echo "Arquivos gerados removidos."
