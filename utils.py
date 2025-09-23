# utils.py

# Importa a biblioteca Scapy para manipulação de pacotes e rotas de rede.
from scapy.all import conf, get_if_hwaddr
# Importa a função de lookup para encontrar o fabricante pelo MAC.
from scapy_oui_lookup import oui_lookup

def detect_active_network():
    """
    Detecta a rede ativa do host e a retorna no formato CIDR.
    Exemplo: 192.168.1.0/24
    """
    try:
        # Obtém a rota padrão da tabela de roteamento do sistema.
        default_route = conf.route.route("0.0.0.0")
        
        # Extrai o nome da interface de rede (ex: 'eth0' ou 'Wi-Fi').
        interface = default_route[0]
        
        # Obtém o endereço IP da interface.
        ip_address = default_route[1]
        
        # Obtém a máscara de sub-rede da interface.
        netmask = default_route[2]
        
        # Constrói o endereço de rede aplicando a máscara ao IP.
        # Scapy lida com isso nativamente, resultando em algo como '192.168.1.0'.
        network_address = conf.route.routes[0][0]

        # Calcula o prefixo da máscara de rede (ex: 24 para 255.255.255.0).
        prefix = sum(bin(int(x)).count('1') for x in netmask.split('.'))

        # Retorna a rede no formato CIDR.
        return f"{network_address}/{prefix}"
    except Exception:
        # Retorna None se não conseguir determinar a rede.
        return None

def get_producer(mac_address):
    """
    Busca o fabricante de um dispositivo com base em seu endereço MAC.
    """
    # Realiza a busca do fabricante usando a biblioteca.
    producer = oui_lookup(mac_address)
    
    # Retorna o fabricante encontrado ou 'Desconhecido' se não for encontrado.
    return producer if producer else "Desconhecido"