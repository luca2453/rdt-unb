import argparse
import csv
import hashlib
import socket
import sys
import time
import random
from datetime import datetime
from typing import TypedDict


SERVER_PORT = 8080
SOCKET_TIMEOUT_SECONDS = 0.5


class MetricaSegmento(TypedDict):
    segment: int
    timestamp: str
    size_bytes: int
    rtt_ms: float
    rtt_estimated_ms: str
    timeout_ms: float
    throughput_kbps: float
    retransmissions: int
    timeout_occurred: int
    window_size: int
    protocol: str
    simulated_loss: int


def criar_socket(timeout: float = SOCKET_TIMEOUT_SECONDS) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    return sock


def parsear_campos(resposta: bytes) -> tuple[str, dict[str, str]]:
    texto = resposta.decode("utf-8")
    partes = texto.split("|")
    tipo = partes[0]
    campos: dict[str, str] = {}
    for campo in partes[1:]:
        if "=" not in campo:
            raise ValueError(f"Campo inválido na resposta: {campo!r}")
        chave, valor = campo.split("=", 1)
        campos[chave] = valor
    return tipo, campos


def ping(sock: socket.socket, servidor: tuple[str, int]) -> tuple[float, float]:
    inicio = time.perf_counter()
    sock.sendto(b"PING", servidor)
    try:
        dados, _ = sock.recvfrom(65507)
    except socket.timeout:
        print("Erro: o servidor demorou a responder ao PING (timeout).")
        return 0.0, 0.0

    rtt = (time.perf_counter() - inicio) * 1000
    try:
        tipo, campos = parsear_campos(dados)
        if tipo != "PONG" or "time" not in campos:
            raise ValueError("resposta não é um PONG válido")
        return rtt, float(campos["time"])
    except (UnicodeDecodeError, ValueError) as erro:
        print(f"Erro: resposta inválida ao PING: {erro}")
        return 0.0, 0.0


def hello(
    sock: socket.socket,
    servidor: tuple[str, int],
    grupo: str,
    arquivo: str,
    segment_size_proposto: int = 512,
) -> dict[str, str]:
    pacote = (
        f"HELLO|grupo={grupo}|segment_size={segment_size_proposto}|file={arquivo}"
    )
    sock.sendto(pacote.encode("utf-8"), servidor)
    try:
        dados, _ = sock.recvfrom(65507)
        tipo, campos = parsear_campos(dados)
    except socket.timeout:
        print("Erro: o servidor demorou a responder ao HELLO (timeout).")
        return {}
    except (UnicodeDecodeError, ValueError) as erro:
        print(f"Erro: resposta inválida ao HELLO: {erro}")
        return {}

    if tipo != "OK":
        print(f"Erro: o servidor não confirmou o HELLO (resposta: {tipo}).")
        return {}
    return campos


def requisitar_segmento(
    sock: socket.socket, servidor: tuple[str, int], seq: int
) -> bytes | None:
    sock.sendto(f"REQ|seq={seq}".encode("utf-8"), servidor)
    try:
        while True:
            dados, _ = sock.recvfrom(65507)
            partes = dados.split(b"|", 3)
            if len(partes) != 4 or partes[0] != b"DATA":
                continue
            try:
                chave, valor = partes[1].split(b"=", 1)
                seq_recebido = int(valor) if chave == b"seq" else -1
            except ValueError:
                continue
            if seq_recebido == seq:
                return partes[3]
    except socket.timeout:
        return None


def receber_data(dados: bytes) -> tuple[int, bytes] | None:
    partes = dados.split(b"|", 3)
    if len(partes) != 4 or partes[0] != b"DATA":
        return None
    try:
        chave, valor = partes[1].split(b"=", 1)
        if chave != b"seq":
            return None
        return int(valor), partes[3]
    except ValueError:
        return None


def transferir_gbn(
    sock: socket.socket,
    servidor: tuple[str, int],
    total_segments: int,
    window_size: int,
    drop_chance: float
) -> tuple[bytearray, list[MetricaSegmento], int]:
    base = 0
    payloads: dict[int, bytes] = {}
    retransmissoes_por_segmento = {seq: 0 for seq in range(total_segments)}
    perdas_simuladas = {seq: 0 for seq in range(total_segments)}
    rtt_por_segmento: dict[int, float] = {}
    recebido_em: dict[int, str] = {}
    enviado_uma_vez: set[int] = set()
    total_retransmissoes = 0

    while base < total_segments:
        fim_janela = min(base + window_size, total_segments)
        janela_completa = False

        while not janela_completa:
            primeiro_envio = base
            if payloads:
                ausentes = [
                    seq for seq in range(base, fim_janela)
                    if seq not in payloads
                ]
                primeiro_envio = min(ausentes) if ausentes else fim_janela

            enviados_em = {}
            for seq in range(primeiro_envio, fim_janela):
                if seq in enviado_uma_vez:
                    retransmissoes_por_segmento[seq] += 1
                    total_retransmissoes += 1
                sock.sendto(f"REQ|seq={seq}".encode("utf-8"), servidor)
                enviados_em[seq] = time.perf_counter()
                enviado_uma_vez.add(seq)

            prazo = time.perf_counter() + SOCKET_TIMEOUT_SECONDS
            while time.perf_counter() < prazo:
                restante = prazo - time.perf_counter()
                sock.settimeout(max(restante, 0.001))
                try:
                    dados, _ = sock.recvfrom(65507)
                except socket.timeout:
                    break

                data = receber_data(dados)
                if data is None:
                    continue
                seq, payload = data
                # Perda simulada: descarta o DATA recebido com probabilidade P
                if random.random() < drop_chance:
                    perdas_simuladas[seq] += 1
                    continue
                if not base <= seq < fim_janela:
                    continue

                if seq not in payloads:
                    payloads[seq] = payload
                    rtt_por_segmento[seq] = (
                        time.perf_counter() - enviados_em.get(seq, time.perf_counter())
                    ) * 1000
                    recebido_em[seq] = datetime.now().astimezone().isoformat(
                        timespec="milliseconds"
                    )
                # Reconfirma duplicatas para que o servidor possa descartar
                # retransmissões sem perder o ACK correspondente.
                sock.sendto(f"ACK|seq={seq}".encode("utf-8"), servidor)

                ausentes = [
                    item for item in range(base, fim_janela)
                    if item not in payloads
                ]
                if not ausentes:
                    janela_completa = True
                    break

            if not janela_completa:
                primeiro_ausente = next(
                    seq for seq in range(base, fim_janela) if seq not in payloads
                )
                print(
                    f"    [!] Timeout GBN na janela {base}-{fim_janela - 1}; "
                    f"retransmitindo a partir do segmento {primeiro_ausente}."
                )

        base = fim_janela

    arquivo_final = bytearray()
    for seq in range(total_segments):
        arquivo_final.extend(payloads[seq])
    metricas: list[MetricaSegmento] = []
    for seq in range(total_segments):
        payload = payloads[seq]
        rtt_seg = rtt_por_segmento[seq]
        metricas.append({
            "segment": seq,
            "timestamp": recebido_em[seq],
            "size_bytes": len(payload),
            "rtt_ms": round(rtt_seg, 3),
            "rtt_estimated_ms": "",
            "timeout_ms": SOCKET_TIMEOUT_SECONDS * 1000,
            "throughput_kbps": round(
                len(payload) * 8 / rtt_seg if rtt_seg else 0.0, 3
            ),
            "retransmissions": retransmissoes_por_segmento[seq],
            "timeout_occurred": int(retransmissoes_por_segmento[seq] > 0),
            "window_size": window_size,
            "protocol": "gbn",
            "simulated_loss": perdas_simuladas[seq],
        })
    sock.settimeout(SOCKET_TIMEOUT_SECONDS)
    return arquivo_final, metricas, total_retransmissoes

def transferir_sv(
    sock: socket.socket,
    servidor: tuple[str, int],
    total_segments: int,
    window_size: int,
    drop_chance: float
) -> tuple[bytearray, list[MetricaSegmento], int]:
    base = 0
    payloads: dict[int, bytes] = {}
    retransmissoes_por_segmento = {seq: 0 for seq in range(total_segments)}
    perdas_simuladas = {seq: 0 for seq in range(total_segments)}
    rtt_por_segmento: dict[int, float] = {}
    recebido_em: dict[int, str] = {}
    enviado_uma_vez: set[int] = set()
    total_retransmissoes = 0

    enviados_em: dict[int, float] = {}

    def send_new():
        nonlocal total_retransmissoes
        assert(base < total_segments)
        for new_seq in range(base, total_segments):
            if new_seq not in payloads and new_seq not in enviados_em:
                if new_seq in enviado_uma_vez:
                    retransmissoes_por_segmento[new_seq] += 1
                    total_retransmissoes += 1
                    #print(f"pedindo seq {new_seq} de novo")
                else:
                    #print(f"pedindo seq {new_seq}")
                    pass
                sock.sendto(f"REQ|seq={new_seq}".encode("utf-8"), servidor)
                enviados_em[new_seq] = time.perf_counter()
                enviado_uma_vez.add(new_seq)
                if len(enviados_em) == window_size:
                    break
    
    def send_all_new():
        remaining = total_segments - len(payloads) - len(enviados_em)
        while len(enviados_em) < window_size and remaining > 0:
            send_new()



    while base < total_segments:
        send_all_new()

        # receber
        oldest_transmition_seq = next(iter(enviados_em))
        oldest_transmition = next(iter(enviados_em.values()))
        for key in enviados_em:
            if enviados_em[key] < oldest_transmition:
                oldest_transmition = enviados_em[key]
                oldest_transmition_seq = key


        prazo = oldest_transmition + SOCKET_TIMEOUT_SECONDS

        restante = prazo - time.perf_counter()
        sock.settimeout(max(restante, 0.001))
        try:
            dados, _ = sock.recvfrom(65507)
        except socket.timeout:
            retransmissoes_por_segmento[oldest_transmition_seq] += 1
            total_retransmissoes += 1
            print(f"seq {oldest_transmition_seq} timeout")

            sock.sendto(f"REQ|seq={oldest_transmition_seq}".encode("utf-8"), servidor)
            enviados_em[oldest_transmition_seq] = time.perf_counter()
            enviado_uma_vez.add(oldest_transmition_seq)
            continue

        data = receber_data(dados)
        if data is None:
            continue
        seq, payload = data
        # Perda simulada: descarta o DATA recebido com probabilidade P
        if random.random() < drop_chance:
            perdas_simuladas[seq] += 1
            continue
        if seq < base:
            continue

        if seq not in payloads:
            payloads[seq] = payload
            rtt_por_segmento[seq] = (
                time.perf_counter() - enviados_em.get(seq, time.perf_counter())
            ) * 1000
            recebido_em[seq] = datetime.now().astimezone().isoformat(
                timespec="milliseconds"
            )
            # Reconfirma duplicatas para que o servidor possa descartar
            # retransmissões sem perder o ACK correspondente.
            sock.sendto(f"ACK|seq={seq}".encode("utf-8"), servidor)

            enviados_em.pop(seq, None)
            while True:
                if base in payloads.keys():
                    base = base + 1
                else:
                    break

    arquivo_final = bytearray()
    for seq in range(total_segments):
        arquivo_final.extend(payloads[seq])
    metricas: list[MetricaSegmento] = []
    for seq in range(total_segments):
        payload = payloads[seq]
        rtt_seg = rtt_por_segmento[seq]
        metricas.append({
            "segment": seq,
            "timestamp": recebido_em[seq],
            "size_bytes": len(payload),
            "rtt_ms": round(rtt_seg, 3),
            "rtt_estimated_ms": "",
            "timeout_ms": SOCKET_TIMEOUT_SECONDS * 1000,
            "throughput_kbps": round(
                len(payload) * 8 / rtt_seg if rtt_seg else 0.0, 3
            ),
            "retransmissions": retransmissoes_por_segmento[seq],
            "timeout_occurred": int(retransmissoes_por_segmento[seq] > 0),
            "window_size": window_size,
            "protocol": "sr",
            "simulated_loss": perdas_simuladas[seq],
        })
    sock.settimeout(SOCKET_TIMEOUT_SECONDS)

    return arquivo_final, metricas, total_retransmissoes

def transferir_saw(
    sock: socket.socket,
    servidor: tuple[str, int],
    total_segments: int,
    window_size: int,
    drop_chance: float
) -> tuple[bytearray, list[MetricaSegmento], int]:
    assert(window_size == 1)
    arquivo_final = bytearray()
    metricas: list[MetricaSegmento] = []
    total_retransmissoes = 0

    for seq in range(total_segments):
        retransmissoes = 0
        perdas_simuladas = 0
        while True:
            inicio_segmento = time.perf_counter()
            payload = requisitar_segmento(sock, servidor, seq)
            rtt_seg = (time.perf_counter() - inicio_segmento) * 1000
            if payload is None:
                retransmissoes += 1
                total_retransmissoes += 1
                continue
            # Perda simulada: descarta o DATA recebido com probabilidade P
            if random.random() < drop_chance:
                perdas_simuladas += 1
                retransmissoes += 1
                total_retransmissoes += 1
                continue

            arquivo_final.extend(payload)
            sock.sendto(f"ACK|seq={seq}".encode("utf-8"), servidor)
            timestamp = datetime.now().astimezone().isoformat(
                timespec="milliseconds"
            )
            throughput_seg = len(payload) * 8 / rtt_seg if rtt_seg else 0.0
            metricas.append({
                "segment": seq,
                "timestamp": timestamp,
                "size_bytes": len(payload),
                "rtt_ms": round(rtt_seg, 3),
                "rtt_estimated_ms": "",
                "timeout_ms": SOCKET_TIMEOUT_SECONDS * 1000,
                "throughput_kbps": round(throughput_seg, 3),
                "retransmissions": retransmissoes,
                "timeout_occurred": int(retransmissoes > 0),
                "window_size": 1,
                "protocol": "saw",
                "simulated_loss": perdas_simuladas,
            })
            if seq % 20 == 0 or seq == total_segments - 1:
                print(
                    f"    [+] Progresso: {seq}/{total_segments - 1} segmentos..."
                )
            break

    return arquivo_final, metricas, total_retransmissoes


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente RDT-UnB")
    parser.add_argument("--server", required=True, help="IP ou hostname do servidor")
    parser.add_argument("--group", required=True, help="Identificador do grupo")
    parser.add_argument(
        "--file", required=True, choices=["small", "medium", "large"],
        help="Arquivo a ser recebido",
    )
    parser.add_argument(
        "--protocol", choices=["saw", "gbn", "sv"], default="saw",
        help="Protocolo de transferência (padrão: saw)",
    )
    parser.add_argument(
        "--window-size", type=int, choices=[1, 4, 8, 16], default=4,
        help="Tamanho da janela do GBN (4, 8 ou 16)",
    )
    parser.add_argument(
        "--drop-chance", type=float, default=0,
        help="Chance de perda de pacote",
    )
    args = parser.parse_args()

    servidor = (args.server, SERVER_PORT)
    sock = criar_socket()
    try:
        print("=== Tarefa 1 — SAW RDT-UnB ===")
        print(f"Servidor alvo: {args.server}:{SERVER_PORT}")
        print(f"Arquivo alvo: {args.file}")
        seed = 12345
        print(f"Seed para perda de pacotes aleatória: {seed}\n")
        random.seed(seed)
        print(f"Chance de perda de pacotes: {args.drop_chance}\n")

        rtt_ping, _ = ping(sock, servidor)
        print("[1] PING")
        print(f"    RTT: {rtt_ping:.2f} ms\n")

        print("[2] HELLO")
        segment_size_proposto = 512
        retorno = hello(sock, servidor, args.group, args.file, segment_size_proposto)
        required = ("segment_size", "total_segments", "file_size", "checksum")
        if not retorno or any(campo not in retorno for campo in required):
            print("    [!] HELLO incompleto. Encerrando conexão.")
            return 1

        try:
            segment_size_oficial = int(retorno["segment_size"])
            total_segments = int(retorno["total_segments"])
            file_size = int(retorno["file_size"])
        except ValueError as erro:
            print(f"    [!] Parâmetros inválidos no OK: {erro}")
            return 1
        checksum_esperado = retorno["checksum"]

        print(f"    Arquivo: {args.file} ({file_size} bytes)")
        print(f"    Checksum MD5: {checksum_esperado}")
        print(f"    Total segmentos: {total_segments}")
        print(
            f"    Tamanho negociado: {segment_size_oficial} bytes "
            f"(proposto: {segment_size_proposto})\n"
        )

        inicio_transferencia = time.perf_counter()
        if args.protocol == "gbn":
            print(
                f"[3] Iniciando transferência Go-Back-N "
                f"({total_segments} segmentos, janela {args.window_size})..."
            )
            arquivo_final, metricas, total_retransmissoes = transferir_gbn(
                sock, servidor, total_segments, args.window_size, args.drop_chance
            )
        elif args.protocol == "sv":
            print(
                f"[3] Iniciando transferência Selective Repeat "
                f"({total_segments} segmentos, janela {args.window_size})..."
            )
            arquivo_final, metricas, total_retransmissoes = transferir_sv(
                sock, servidor, total_segments, args.window_size, args.drop_chance
            )

        else:
            print(
                f"[3] Iniciando transferência Stop-and-Wait "
                f"({total_segments} segmentos)..."
            )
            arquivo_final, metricas, total_retransmissoes = transferir_saw(
                sock, servidor, total_segments, args.window_size, args.drop_chance
            )

        tempo_total = time.perf_counter() - inicio_transferencia
        md5_calculado = hashlib.md5(arquivo_final).hexdigest()

        print("\n[4] Verificando integridade...")
        print(f"    MD5 esperado:  {checksum_esperado}")
        print(f"    MD5 calculado: {md5_calculado}")
        if md5_calculado != checksum_esperado:
            print("    [!] O arquivo recebido está corrompido.")
            return 1

        print("\n[5] Encerrando sessão...")
        print("    Integridade confirmada localmente (MD5).")

        timestamp_arquivo = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_csv = f"metrics_{args.group}_{args.protocol}_{timestamp_arquivo}.csv"
        fieldnames = [
            "segment", "timestamp", "size_bytes", "rtt_ms", "rtt_estimated_ms",
            "timeout_ms", "throughput_kbps", "retransmissions",
            "timeout_occurred", "window_size", "protocol", "simulated_loss",
        ]
        with open(nome_csv, "w", newline="", encoding="utf-8") as arquivo_csv:
            writer = csv.DictWriter(arquivo_csv, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metricas)

        nome_saida = f"recebido_{args.group}_{args.file}.bin"
        with open(nome_saida, "wb") as arquivo_binario:
            arquivo_binario.write(arquivo_final)

        rtt_medio = sum(float(m["rtt_ms"]) for m in metricas) / len(metricas)
        throughput_kbps = len(arquivo_final) * 8 / 1000 / tempo_total
        teorico_kbps: float

        if args.protocol == "gbn":
            teorico_kbps= args.window_size*(segment_size_oficial * 8) / rtt_medio
        elif args.protocol == "sv":
            teorico_kbps= args.window_size*(segment_size_oficial * 8) / rtt_medio
        else:
            teorico_kbps= segment_size_oficial * 8 / rtt_medio


        print(f"\n    CSV salvo em: {nome_csv}")
        print(f"    Arquivo salvo em: {nome_saida}")
        print("\n" + "=" * 45)
        nome_protocolo = "STOP-AND-WAIT"
        if args.protocol == "gbn":
            nome_protocolo = "GO-BACK-N"
        elif args.protocol == "sv":
            nome_protocolo = "SELECTIVE-REPEAT"
        print(f" RELATÓRIO DA TRANSFERÊNCIA ({nome_protocolo})")
        print("=" * 45)
        print(f" Arquivo recebido:  {args.file}")
        print(f" Tamanho total:     {len(arquivo_final)} bytes")
        print(f" Tempo decorrido:   {tempo_total:.2f} segundos")
        print(f" Throughput médio:  {throughput_kbps:.2f} kbps")
        print(f" RTT médio:         {rtt_medio:.2f} ms")
        
        if args.protocol == "gbn":
            print(f" Throughput teórico: {teorico_kbps:.2f} kbps window_size*(segment_size*8/RTT)")
        elif args.protocol == "sv":
            print(f" Throughput teórico: {teorico_kbps:.2f} kbps window_size*(segment_size*8/RTT)")
        else:
           print(f" Throughput teórico: {teorico_kbps:.2f} kbps (segment_size*8/RTT)")

        print(f" Retransmissões:    {total_retransmissoes}")
        print(f" MD5 calculado:     {md5_calculado}")
        print(" Integridade (MD5): SUCESSO (Sem corrupção)")
        print("=" * 45)
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
