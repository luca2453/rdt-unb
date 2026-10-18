all: run

run:
	python3 client.py --server 137.131.178.229 --group grupo12 --file small

test:
	python3 client_teste.py
