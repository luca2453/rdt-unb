PYTHON ?= python3
SERVER ?= 137.131.178.229
GROUP ?= grupo12
FILE ?= small
WINDOW ?= 4
CSV ?=

.PHONY: all help run saw gbn gbn4 gbn8 gbn16 test check syntax graph

all: help

help:
	@echo "Comandos disponíveis:"
	@echo "  make saw       - executa Stop-and-Wait"
	@echo "  make gbn       - executa Go-Back-N (janela configurável)"
	@echo "  make gbn4      - executa Go-Back-N com janela 4"
	@echo "  make gbn8      - executa Go-Back-N com janela 8"
	@echo "  make gbn16     - executa Go-Back-N com janela 16"
	@echo "  make sv       - executa Selective Repeat (janela configurável)"
	@echo "  make sv4      - executa Selective Repeat com janela 4"
	@echo "  make sv8      - executa Selective Repeat com janela 8"
	@echo "  make sv16     - executa Selective Repeat com janela 16"
	@echo "  make test      - executa o teste básico do servidor"
	@echo "  make check     - verifica a sintaxe dos arquivos Python"
	@echo "  make graph CSV=metrics_...csv - gera gráficos do CSV"
	@echo ""
	@echo "Parâmetros: SERVER=$(SERVER) GROUP=$(GROUP) FILE=$(FILE) WINDOW=$(WINDOW)"

run: saw

saw:
	$(PYTHON) client.py --server $(SERVER) --group $(GROUP) --file $(FILE) --protocol saw

gbn:
	$(PYTHON) client.py --server $(SERVER) --group $(GROUP) --file $(FILE) --protocol gbn --window-size $(WINDOW)

gbn4:
	$(MAKE) gbn WINDOW=4

gbn8:
	$(MAKE) gbn WINDOW=8

gbn16:
	$(MAKE) gbn WINDOW=16

sv:
	$(PYTHON) client.py --server $(SERVER) --group $(GROUP) --file $(FILE) --protocol sv --window-size $(WINDOW)

sv4:
	$(MAKE) sv WINDOW=4

sv8:
	$(MAKE) sv WINDOW=8

sv16:
	$(MAKE) sv WINDOW=16

test:
	$(PYTHON) rdt_diagnostico.py

syntax:
	$(PYTHON) -m py_compile client.py rdt_diagnostico.py graficos.py

check: syntax
	git diff --check

graph:
ifndef CSV
	$(error informe o CSV, por exemplo: make graph CSV=metrics_grupo12_saw_20261026_012200.csv)
endif
	$(PYTHON) graficos.py $(CSV)
