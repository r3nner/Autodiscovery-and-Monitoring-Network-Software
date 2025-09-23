# discovery.py

# Importa as funções da biblioteca Scapy para criar e enviar pacotes.
from scapy.all import ARP, Ether, srp, IP, ICMP, sr1, conf

# Importa a biblioteca para medir o tempo de execução.
import time

# Importa as funções de apoio do nosso projeto.
import utils
# Importa as variáveis de configuração do nosso projeto.
import config

# Define o nível de verbosidade do Scapy para não exibir mensagens desnecessárias.
conf.verb = 0

def discovery_arp(network_cidr):
    """
    Executa uma varredura ARP na rede especificada para descobrir dispositivos.
    Aceita a rede no formato CIDR (ex: '192.168.1.0/24').
    """
    # Cria uma lista vazia para armazenar os dispositivos encontrados.
    discovered_devices = []

    # Cria um pacote de requisição ARP (ARP request).
    # Define o IP de destino (pdst) para toda a faixa de rede CIDR.
    arp_request = ARP(pdst=network_cidr)

    # Cria um frame Ethernet para encapsular a requisição ARP.
    # Define o MAC de destino (dst) como broadcast para alcançar todos na rede.
    broadcast = Ether(dst="ff:ff:ff:ff:ff")

    # Combina o frame Ethernet e a requisição ARP em um único pacote.
    arp_request_broadcast = broadcast / arp_request

    # Envia o pacote e aguarda as respostas (Send and Receive Packet).
    # Define um timeout a partir do arquivo de configuração.
    # A função srp retorna uma tupla com os pacotes respondidos e não respondidos.
    answered_list, _ = srp(arp_request_broadcast, timeout=config.SCAN_TIMEOUT)

    # Itera sobre a lista de respostas recebidas.
    for sent, received in answered_list:
        # Extrai o endereço IP da resposta.
        ip = received.psrc
        # Extrai o endereço MAC da resposta.
        mac = received.hwsrc
        # Usa uma função utilitária para obter o fabricante a partir do MAC.
        producer = utils.get_producer(mac)

        # Adiciona as informações do dispositivo em um dicionário.
        device = {
            'ip': ip,
            'mac': mac,
            'producer': producer
        }
        # Adiciona o dicionário do dispositivo à lista de descobertos.
        discovered_devices.append(device)

    # Retorna a lista completa de dispositivos que responderam ao scan.
    return discovered_devices

def discovery_ping(ip_address):
    """
    Verifica o status (online/offline) e a latência de um único IP via ICMP Ping.
    """
    # Cria um pacote IP/ICMP (Echo Request) para o endereço de destino.
    packet = IP(dst=ip_address) / ICMP()

    # Registra o tempo de início antes de enviar o pacote.
    start_time = time.time()
    
    # Envia o pacote e aguarda por uma única resposta (Send and Receive 1).
    # Define um timeout para não esperar indefinidamente.
    response = sr1(packet, timeout=config.SCAN_TIMEOUT)
    
    # Registra o tempo de término após receber a resposta ou o timeout.
    end_time = time.time()

    # Verifica se uma resposta foi recebida.
    if response:
        # Calcula a latência em milissegundos.
        latency = (end_time - start_time) * 1000
        # Retorna o status 'online' e a latência calculada.
        return {'status': 'online', 'latency': round(latency, 2)}
    else:
        # Retorna o status 'offline' e latência nula se não houver resposta.
        return {'status': 'offline', 'latency': None}