# python3 client.py --server 137.131.178.229 --group grupo12 --file small

import argparse
import csv
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
    # 1. Leitura dos argumentos de linha de comando (argparse)
    parser = argparse.ArgumentParser(description="Cliente Stop-and-Wait (SAW) - RDT-UnB")
    parser.add_argument("--server", required=True, help="IP do servidor RDT-UnB")
    parser.add_argument("--group", required=True, help="Nome do grupo (campo grupo= do HELLO)")
    parser.add_argument("--file", required=True, choices=["small", "medium", "large"],
                        help="Arquivo a ser recebido")
    args = parser.parse_args()  # sem --group, o argparse aborta com erro

    servidor_ip = args.server
    grupo = args.group
    arquivo = args.file

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
    
    metricas = []  # uma linha por segmento para o CSV

    for seq in range(total_segments):
        retx_seg = 0
        while True:
            # 1. Envia REQ e aguarda o pacote DATA (RTT medido nesta tentativa)
            t0 = time.perf_counter()
            payload = requisitar_segmento(sock, servidor, seq)
            rtt_seg = (time.perf_counter() - t0) * 1000  # ms
            
            if payload:
                throughput_seg = (len(payload) * 8 / 1000) / (rtt_seg / 1000)  # kbps
                metricas.append({
                    "seq": seq,
                    "rtt_ms": round(rtt_seg, 3),
                    "throughput_kbps": round(throughput_seg, 3),
                    "retransmissoes": retx_seg,
                    "timeout_ocorrido": int(retx_seg > 0),
                    "payload_bytes": len(payload),
                    "t_fim_s": round(time.time() - inicio_transferencia, 6),
                })
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
                # O timeout estourou. Registra a retransmissão e tenta de novo
                total_retransmissoes += 1
                retx_seg += 1

    tempo_total = time.time() - inicio_transferencia

    # Salva métricas por segmento em CSV
    nome_csv = f"metricas_{grupo}_{arquivo}.csv"
    with open(nome_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(metricas[0].keys()))
        w.writeheader()
        w.writerows(metricas)
    rtt_medio = sum(m["rtt_ms"] for m in metricas) / len(metricas)
    teorico_kbps = (segment_size_oficial * 8 / 1000) / (rtt_medio / 1000)
    print(f"\n    CSV salvo em: {nome_csv}")

    # Passo 4 - Validação de Integridade
    print("\n[4] Verificando integridade...")
    md5_calculado = hashlib.md5(arquivo_final).hexdigest()
    
    print(f"    MD5 esperado:  {checksum_esperado}")
    print(f"    MD5 calculado: {md5_calculado}")

    if md5_calculado == checksum_esperado:
        status_md5 = "SUCESSO (Sem corrupção)"
    else:
        status_md5 = "ERRO (Checksum não coincide)"

    # Salva o arquivo recebido em disco (evidência da transferência)
    nome_saida = f"recebido_{grupo}_{arquivo}.bin"
    with open(nome_saida, "wb") as f:
        f.write(arquivo_final)
    print(f"    Arquivo salvo em: {nome_saida}")
        
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
    print(f" RTT médio:         {rtt_medio:.2f} ms")
    print(f" Throughput teórico:{teorico_kbps:.2f} kbps  (segment_size*8/RTT_medio)")
    print(f" Retransmissões:    {total_retransmissoes} pacotes perdidos")
    print(f" MD5 calculado:     {md5_calculado}")
    print(f" Integridade (MD5): {status_md5}")
    print("="*45 + "\n")
    
    
if __name__ == "__main__":
    main()