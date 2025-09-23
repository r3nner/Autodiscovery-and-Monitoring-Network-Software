# utils.py

# Importa a biblioteca Scapy para manipulação de pacotes e rotas de rede.
from scapy.all import conf, get_if_hwaddr
# Importa as classes da biblioteca correta para buscar o fabricante do MAC.
from mac_vendor_lookup import MacLookup, VendorNotFoundError

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
    try:
        # Realiza a busca do fabricante usando a biblioteca correta.
        return MacLookup().lookup(mac_address)
    except VendorNotFoundError:
        # Retorna 'Desconhecido' se o fabricante do MAC não for encontrado.
        return "Desconhecido"