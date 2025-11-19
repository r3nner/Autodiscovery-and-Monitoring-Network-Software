# discovery.py
"""
Módulo de descoberta e identificação de dispositivos de rede.

Implementa funções de varredura e análise usando múltiplos protocolos:
- ARP scanning (scapy.arping) para descoberta de hosts ativos
- ICMP ping para teste de conectividade
- SNMPv2c/v3 para identificação de papel (roteador/host) e informações de sistema

Retorna estruturas padronizadas para integração com database.py
"""

import subprocess  # Execução comandos de ping do sistema operacional
import platform  # Detecção o sistema operacional (Windows, Linux, macOS)
from scapy.all import arping  # Realização scan ARP na rede e descobrir dispositivos
from pysnmp.hlapi import (
    getCmd, 
    SnmpEngine, 
    CommunityData, 
    UdpTransportTarget, 
    ContextData, 
    ObjectType, 
    ObjectIdentity
)
import re  # Para extração de TTL da saída do ping
import socket  # Para scan de portas TCP

import config  # Importa para usar as configurações de SNMP

def discovery_arp(network_cidr):
    """
    Executa um scan ARP na rede para descobrir hosts ativos.
    Retorna uma lista de dicionários, cada um com 'ip' e 'mac'.
    """
    
    print(f"(Discovery: Executando ARP scan em {network_cidr}...)")
    try:
        # O timeout é herdado do config, que é ajustado em runtime pelo main.py
        ans, unans = arping(network_cidr, timeout=config.SCAN_TIMEOUT, verbose=False)
        devices = []
        for sent, received in ans:
            devices.append({
                'ip': received.psrc,
                'mac': received.hwsrc
            })
        print(f"(Discovery: ARP encontrou {len(devices)} dispositivo(s).)")
        return devices
    except Exception as e:
        print(f"Erro no scan ARP: {e}")
        return []

def discovery_ping(ip, count=10):
    """
    Verifica se um IP está respondendo, calcula TTL, Latência Média e Perda de Pacotes.
    Envia 'count' pacotes (padrão 10).
    
    Retorna dicionário com: 'status', 'ttl', 'avg_latency' (ms), 'packet_loss' (%)
    """
    try:
        system_os = platform.system().lower()
        command = ['ping']
        
        if system_os == 'windows':
            # Windows: -n (count), -w (timeout em ms por pacote)
            command.extend(['-n', str(count), '-w', '200', ip])
        else:
            # Linux/Mac: -c (count), -W (timeout total ou por pacote dependendo da versão)
            # -i 0.2: Intervalo de 200ms entre pacotes (acelera o scan de 10s para 2s)
            # Requer sudo, mas você já está rodando como root.
            command.extend(['-c', str(count), '-i', '0.2', '-W', '1', ip])
        
        # Executa o comando e captura a saída (stdout)
        # stderr é redirecionado para DEVNULL para não sujar o terminal
        response_output = subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True)
        
        result = {
            'status': 'online',
            'ttl': None,
            'avg_latency': 0.0,
            'packet_loss': 0.0
        }

        # 1. Extração do TTL
        ttl_match = re.search(r'(?i)ttl=(\d+)', response_output)
        if ttl_match:
            result['ttl'] = int(ttl_match.group(1))

        # 2. Extração de Perda de Pacotes (Packet Loss)
        # Linux: "0% packet loss" | Windows: "(0% loss)"
        loss_match = re.search(r'(\d+)%\s+(packet\s+)?loss', response_output)
        if loss_match:
            result['packet_loss'] = float(loss_match.group(1))
        
        # Se 100% de perda, marca como offline (mesmo que o comando não tenha falhado por código de erro)
        if result['packet_loss'] == 100.0:
            return {'status': 'offline', 'ttl': None, 'avg_latency': None, 'packet_loss': 100.0}

        # 3. Extração de Latência Média (Average RTT)
        # Linux: "rtt min/avg/max/mdev = 2.123/4.567/..."
        # Windows: "Average = 4ms"
        if system_os == 'windows':
            avg_match = re.search(r'Average = (\d+)ms', response_output)
            if avg_match:
                result['avg_latency'] = float(avg_match.group(1))
        else:
            # Pega o valor entre as barras: min/AVG/max
            avg_match = re.search(r'rtt\s+min/avg/max/mdev\s+=\s+.*?/([\d.]+)/', response_output)
            if avg_match:
                result['avg_latency'] = float(avg_match.group(1))

        return result

    except (subprocess.CalledProcessError, FileNotFoundError):
        # Se o ping retornar código de erro (host inalcançável)
        return {
            'status': 'offline', 
            'ttl': None, 
            'avg_latency': None, 
            'packet_loss': 100.0
        }
    except Exception as e:
        print(f"Erro inesperado no ping: {e}")
        return {'status': 'offline', 'ttl': None, 'avg_latency': None, 'packet_loss': 100.0}
    
def discovery_snmp_basic(ip):
    """
    Tenta obter informações básicas de um dispositivo via SNMP,
    incluindo nome, descrição e se é um roteador (ipForwarding).
    """
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(config.SNMP_COMMUNITY, mpModel=1),
        UdpTransportTarget((ip, config.SNMP_PORT), timeout=config.SNMP_TIMEOUT, retries=config.SNMP_RETRIES),
        ContextData(),
        ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysName', 0)),
        ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)),
        ObjectType(ObjectIdentity('IP-MIB', 'ipForwarding', 0)) 
    )

    try:
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication or errorStatus:
            return {}

        snmp_data = {}
        for varBind in varBinds:
            key = varBind[0].getMibSymbol()[0]
            value = varBind[1]

            if key == 'sysName':
                snmp_data['snmp_name'] = str(value)
            elif key == 'sysDescr':
                snmp_data['snmp_description'] = str(value)
            elif key == 'ipForwarding':
                # O valor 1 significa 'forwarding' (é um roteador)
                # O valor 2 significa 'not-forwarding' (é um host)
                if int(value) == 1:
                    snmp_data['role'] = 'Roteador'
                else:
                    snmp_data['role'] = 'Host'
        
        # Se a role não foi descoberta via ipForwarding, deixa em branco
        if 'role' not in snmp_data:
            snmp_data['role'] = 'N/A'

        return snmp_data

    except Exception:
        return {}


def discovery_tcp_ports(ip):
    """
    Executa um scan rápido em portas TCP predefinidas para um IP.
    Retorna um dicionário com uma lista de portas abertas.
    """
    open_ports = []
    for port in config.PORTS_TO_SCAN:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(config.PORT_SCAN_TIMEOUT)
        # result == 0 indica sucesso (porta aberta), result > 0 indica erro
        result = sock.connect_ex((ip, port))
        if result == 0:
            open_ports.append(port)
        sock.close()
    return {'open_ports': open_ports}