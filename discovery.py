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
from pysnmp.hlapi import *  # Comunicação SNMP e obter informações dos dispositivos

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

def discovery_ping(ip):
    """
    Verifica se um IP está respondendo ao ping.
    Retorna um dicionário com 'status' ('online' ou 'offline').
    """
    try:
        # Constrói o comando de ping de forma compatível com Windows, Linux e macOS
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', '-w', '1', ip]
        
        # Executa o comando sem mostrar a saída no console
        response = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if response.returncode == 0:
            return {'status': 'online'}
        else:
            return {'status': 'offline'}
    except Exception:
        return {'status': 'offline'}

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