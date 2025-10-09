# utils.py

import ipaddress
import netifaces  # Importa a biblioteca correta
from oui_db import OUI_DATABASE

def get_producer(mac_address):
    """
    Busca o fabricante de um dispositivo usando o dicionário local pré-carregado.
    """
    # Formata o MAC para a busca: 'd8:32:14:27:7d:17' -> 'D83214'
    prefixo_busca = mac_address.replace(':', '').upper()[:6]
    
    # A busca é feita diretamente no dicionário importado.
    return OUI_DATABASE.get(prefixo_busca, "Desconhecido")

def detect_active_network():
    """
    Detecta a rede ativa do host de forma precisa usando a biblioteca netifaces.
    Remove a necessidade de adivinhar a máscara de rede.
    """
    try:
        # 1. Encontra o gateway padrão e a interface associada
        gateways = netifaces.gateways()
        # Procura por um gateway padrão na família de endereços IPv4 (AF_INET)
        default_gateway_info = gateways.get('default', {}).get(netifaces.AF_INET)

        if not default_gateway_info:
            raise ValueError("Não foi possível determinar o gateway padrão IPv4. Verifique a conexão de rede.")

        # O segundo elemento da tupla é o nome da interface (ex: 'eth0', 'wlan0')
        interface_name = default_gateway_info[1]

        # 2. Obtém os endereços da interface encontrada
        if_addresses = netifaces.ifaddresses(interface_name)
        ipv4_info_list = if_addresses.get(netifaces.AF_INET)

        if not ipv4_info_list:
            raise ValueError(f"A interface {interface_name} não possui um endereço IPv4 configurado.")

        # 3. Pega o endereço IP e a máscara de rede
        # Usamos o primeiro dicionário da lista, que contém 'addr' e 'netmask'
        ipv4_info = ipv4_info_list[0]
        ip_address = ipv4_info['addr']
        netmask = ipv4_info['netmask']
        
        # 4. Usa a biblioteca ipaddress para calcular a rede no formato CIDR
        # 'strict=False' é crucial aqui: ele calcula o endereço de rede (ex: 192.168.1.0)
        # a partir de um endereço de host (ex: 192.168.1.104) e sua máscara.
        network = ipaddress.IPv4Network(f"{ip_address}/{netmask}", strict=False)
        
        return str(network)
    
    except Exception as e:
        print(f"Erro ao detectar a rede automaticamente: {e}")
        return None


def get_default_gateway_ip():
    """Retorna o IP do gateway padrão IPv4 (roteador) ou None se não houver."""
    try:
        gateways = netifaces.gateways()
        default_ipv4 = gateways.get('default', {}).get(netifaces.AF_INET)
        if not default_ipv4:
            return None
        gw_ip = default_ipv4[0]
        return gw_ip
    except Exception:
        return None