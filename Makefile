all: run

run:
	python3 client.py --server 26.209.234.215 --group grupo12 --file small

test:
	python3 rdt_diagnostico.py
