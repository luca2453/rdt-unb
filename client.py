import socket
import time

SERVIDOR = "137.131.178.229"
PORTA    = 8080
GRUPO    = "grupo12"

def criar_socket(timeout=5.0):
    # cria e configura o socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    
    return sock

def ping(sock, servidor):
    # envia PING, mede RTT, retorna float em ms
    inicio = time.time()
    
    sock.sendto(b"PING", servidor)
    try:
        dados, _ = sock.recvfrom(65507)
    except socket.timeout:
        print("Erro: O servidor demorou a responder no PING (Timeout).")
        return 0.0, 0.0
    
    rtt = (time.time() - inicio) * 1000
    
    resposta = dados.decode("utf-8")
    _, tempo_str = resposta.split("|time=")
    tempo_servidor = float(tempo_str)
    
    return rtt, tempo_servidor

def hello(sock: socket.socket, servidor: tuple, grupo: str):
    # envia HELLO, parseia OK, retorna dict com os campos
    pacote = f"HELLO|grupo={grupo}|segment_size=512|file=small"
    sock.sendto(pacote.encode("utf-8"), servidor)
    
    try:
        dados, _ = sock.recvfrom(65507)
    except socket.timeout:
        print("Erro: O servidor demorou a responder (Timeout).")
        return {}
    
    resposta = dados.decode("utf-8")
    
    campos = {}
    
    for campo in resposta.split("|")[1:]:
        chave, valor = campo.split("=",1)
        campos[chave] = valor
    
    return campos

def requisitar_segmento(sock: socket.socket, servidor: tuple, seq: int=0):
    # envia REQ seq=0, recebe DATA, retorna bytes do payload
    
    pacote = f"REQ|seq={seq}"
    sock.sendto(pacote.encode("utf-8"), servidor)
    
    try:
        dados, _ = sock.recvfrom(65507)
    except socket.timeout:
        print("Erro: O servidor demorou a responder no REQ (Timeout).")
        return b""
    
    partes = dados.split(b"|", 3)
    
    if len(partes) == 4 and partes[0] == b"DATA":
        return partes[3]
        
    return b""
    

def main():
    sock = criar_socket()
    servidor = (SERVIDOR, PORTA)
    

    print("=== Tarefa 0 — RDT-UnB Explorer ===")
    print(f"Servidor: {SERVIDOR}:{PORTA}")
    print()

    # Passo 1 — PING
    rtt, tempo_servidor = ping(sock, servidor)
    print(f"[1] PING")
    print(f"    RTT: {rtt:.2f} ms\n")

    # Passo 2 — HELLO
    print(f"[2] HELLO")
    retorno = hello(sock, servidor, GRUPO)
    
    if not retorno:
        print("    [!] Erro de timeout no HELLO! Encerrando conexão.")
        return
    
    print(f"    Arquivo:         small ({retorno['file_size']} bytes = {int(retorno['file_size'])//1024} KB)")
    print(f"    Checksum MD5:    {retorno['checksum']}")
    print(f"    Total segmentos: {retorno['total_segments']}")
    print(f"    Tamanho segmento: {retorno['segment_size']} bytes\n")
    

    # Passo 3 — REQ
    print("[3] REQ seg=0")
    payload = requisitar_segmento(sock, servidor, 0)
    
    if not payload:
        print("    [!] Falha ao receber o segmento. Encerrando conexão.")
        return
        
    primeiros = payload[:8]
    print(f"    Payload recebido: {len(payload)} bytes")
    hex_str = " ".join(f"{b:02x}" for b in primeiros)
    print(f"    Primeiros 8 bytes: {hex_str}")

if __name__ == "__main__":
    main()