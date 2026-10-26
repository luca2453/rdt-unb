all: run

run:
	python3 client.py --server 189.6.60.236 --group grupo12 --file small

test:
	python3 client_teste.py
