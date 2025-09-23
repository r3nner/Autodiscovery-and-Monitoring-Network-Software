# utils.py

import ipaddress
from scapy.all import conf

# Importa DIRETAMENTE o dicionário pré-processado do arquivo gerado.
# O programa agora depende de 'oui_db.py' e não mais de 'oui.txt'.
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
    Detecta a rede ativa do host com a lógica de correção para /32.
    """
    try:
        default_route = conf.route.route("0.0.0.0", verbose=False)
        if not default_route or len(default_route) < 1:
             raise ValueError("Não foi possível determinar a rota padrão.")
        
        interface_name = default_route[0]

        for iface in conf.ifaces.values():
            if iface.name == interface_name:
                ip_with_prefix = iface.ip
                if ip_with_prefix:
                    interface = ipaddress.IPv4Interface(ip_with_prefix)
                    network = interface.network
                    
                    if network.prefixlen == 32:
                        ip_host = str(network.network_address)
                        network_cidr = ipaddress.IPv4Network(f"{ip_host}/24", strict=False)
                        print(f"AVISO: Rede detectada como /32. Assumindo a rede padrão {network_cidr} para o scan.")
                        return str(network_cidr)
                    
                    return str(network)
        
        raise ValueError(f"Não foi possível encontrar detalhes para a interface {interface_name}.")
    except Exception as e:
        print(f"Erro ao detectar a rede: {e}")
        return None