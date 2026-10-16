# python3 client.py --server 137.131.178.229 --group grupo12 --file small

import sys
import socket
import time
import hashlib

def criar_socket(timeout=0.5):
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

def hello(sock: socket.socket, servidor: tuple, grupo: str, arquivo: str, segment_size_proposto: int = 512):
    # Envia HELLO dinâmico, parseia OK, retorna dict com os campos
    pacote = f"HELLO|grupo={grupo}|segment_size={segment_size_proposto}|file={arquivo}"
    sock.sendto(pacote.encode("utf-8"), servidor)
    
    try:
        dados, _ = sock.recvfrom(65507)
    except socket.timeout:
        print("Erro: O servidor demorou a responder no HELLO (Timeout).")
        return {}
    
    resposta = dados.decode("utf-8")
    
    campos = {}
    for campo in resposta.split("|")[1:]:
        chave, valor = campo.split("=", 1)
        campos[chave] = valor
    
    return campos

def requisitar_segmento(sock: socket.socket, servidor: tuple, seq: int=0):
    pacote = f"REQ|seq={seq}"
    sock.sendto(pacote.encode("utf-8"), servidor)
    
    try:
        # Fica num loop interno apenas a ler os pacotes que chegam
        while True:
            dados, _ = sock.recvfrom(65507)
            partes = dados.split(b"|", 3)
            
            if len(partes) == 4 and partes[0] == b"DATA":
                _, seq_recebido_str = partes[1].split(b"=")
                seq_recebido = int(seq_recebido_str)
                
                # Se for o pacote certo, devolve o payload
                if seq_recebido == seq:
                    return partes[3]
                
                # Se for um pacote antigo (seq_recebido != seq), o loop continua
                # e ele lê o próximo pacote da placa de rede sem reenviar o REQ.

    except socket.timeout:
        # Só retorna erro se passar o tempo total de espera sem chegar o pacote certo
        return b""
    

def main():
    # 1. Leitura manual dos argumentos com sys.argv
    if len(sys.argv) < 7:
        print("Uso correto: python3 client.py --server <IP> --group <grupo> --file <arquivo>")
        return

    servidor_ip = ""
    grupo = ""
    arquivo = ""

    # Captura argumentos
    for i in range(1, len(sys.argv)):
        if sys.argv[i] == "--server" and i + 1 < len(sys.argv):
            servidor_ip = sys.argv[i + 1]
        elif sys.argv[i] == "--group" and i + 1 < len(sys.argv):
            grupo = sys.argv[i + 1]
        elif sys.argv[i] == "--file" and i + 1 < len(sys.argv):
            arquivo = sys.argv[i + 1]

    if not servidor_ip or not grupo or not arquivo:
        print("Erro: Faltam argumentos obrigatórios (--server, --group, --file).")
        return

    sock = criar_socket(timeout=0.5)
    servidor = (servidor_ip, 8080)
    
    print("=== Tarefa 1 — SAW RDT-UnB ===")
    print(f"Servidor alvo: {servidor_ip}:8080")
    print(f"Arquivo alvo: {arquivo}\n")

    # Passo 1 — PING 
    rtt, tempo_servidor = ping(sock, servidor)
    print(f"[1] PING")
    print(f"    RTT: {rtt:.2f} ms\n")

    # Passo 2 — HELLO
    print(f"[2] HELLO")
    seg_size_proposto = 512
    
    retorno = hello(sock, servidor, grupo, arquivo, seg_size_proposto)
    
    if not retorno:
        print("    [!] Erro de timeout no HELLO! Encerrando conexão.")
        return
    
    # Negociacao concluida
    segment_size_oficial = int(retorno['segment_size'])
    total_segments = int(retorno['total_segments'])
    file_size = int(retorno['file_size'])
    checksum_esperado = retorno['checksum']
    
    print(f"    Arquivo:         {arquivo} ({file_size} bytes = {file_size//1024} KB)")
    print(f"    Checksum MD5:    {checksum_esperado}")
    print(f"    Total segmentos: {total_segments}")
    print(f"    Tamanho negociado: {segment_size_oficial} bytes (Proposto: {seg_size_proposto})\n")
    
    # Passo 3 - Loop SAW (REQ -> DATA -> ACK)
    print(f"[3] Iniciando transferência Stop-and-Wait ({total_segments} segmentos)...")
    
    arquivo_final = bytearray()
    total_retransmissoes = 0
    inicio_transferencia = time.time()
    
    for seq in range(total_segments):
        while True:
            # 1. Envia REQ e aguarda o pacote DATA
            payload = requisitar_segmento(sock, servidor, seq)
            
            if payload:
                # 2. Recebeu com sucesso
                arquivo_final.extend(payload)
                
                # 3. Envia ACK
                pacote_ack = f"ACK|seq={seq}"
                sock.sendto(pacote_ack.encode("utf-8"), servidor)
                
                # Mostra o progresso a cada 20 segmentos (incluindo o segmento 0)
                if seq % 20 == 0 or seq == total_segments - 1:
                    print(f"    [+] Progresso: {seq}/{total_segments - 1} segmentos...")
                
                break 
                
            else:
                # O timeout estourou. Registra a retransmissão global e tenta de novo silenciosamente
                total_retransmissoes += 1

    tempo_total = time.time() - inicio_transferencia

    # Passo 4 - Validação de Integridade
    print("\n[4] Verificando integridade...")
    md5_calculado = hashlib.md5(arquivo_final).hexdigest()
    
    if md5_calculado == checksum_esperado:
        status_md5 = "SUCESSO (Sem corrupção)"
    else:
        status_md5 = "ERRO (Checksum não coincide)"
        
    # Passo 5 - Relatório Final
    # Calcula o throughput em kbps (kilobits por segundo)
    throughput_kbps = (len(arquivo_final) * 8 / 1000) / tempo_total

    print("\n" + "="*45)
    print(" RELATÓRIO DA TRANSFERÊNCIA (STOP-AND-WAIT)")
    print("="*45)
    print(f" Arquivo recebido:  {arquivo}")
    print(f" Tamanho total:     {len(arquivo_final)} bytes")
    print(f" Tempo decorrido:   {tempo_total:.2f} segundos")
    print(f" Throughput médio:  {throughput_kbps:.2f} kbps")
    print(f" Retransmissões:    {total_retransmissoes} pacotes perdidos")
    print(f" Integridade (MD5): {status_md5}")
    print("="*45 + "\n")
    
    
if __name__ == "__main__":
    main()