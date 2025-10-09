# main.py
"""
Módulo principal do sistema de autodescoberta de rede.

Responsável pela orquestração dos componentes do sistema, incluindo:
- Thread de monitoramento contínuo (polling adaptativo)
- Gerenciamento de estado compartilhado entre componentes
- Interface CLI para controle interativo
"""

import json
import threading
import time

import cli
import config
import database
import discovery
import utils
from oui_db import OUI_DATABASE


def _write_status_file(shared_state, devices):

    """Escreve o estado atual e a lista de dispositivos em um arquivo JSON."""

    status_data = {
        "control": {
            "targetNetwork": shared_state.get('network_cidr') or 'auto'
        },
        "status": {
            "nextScanInSeconds": shared_state.get('next_scan_in', 0),
            "lastScanDeviceCount": shared_state.get('device_count', 0)
        },
        "devices": devices
    }
    try:
        with open('status.json', 'w') as f:
            json.dump(status_data, f, indent=4, default=str)
    except Exception as e:
        print(f"(Erro ao escrever arquivo de status: {e})")


def run_orchestrator(shared_state, lock):
    """
    Contém a lógica principal que roda em segundo plano (thread).
    Usa SNMP para identificar o papel e o dicionário local para o fabricante.
    """
    time.sleep(config.INITIAL_DELAY)
    last_device_count = -1
    
    while shared_state.get('running', True):
        with lock:
            is_paused = shared_state.get('status') == 'pausado'
            is_forced = shared_state.get('force_scan', False)

        if is_paused and not is_forced:
            time.sleep(1)
            continue
        
        print("\n(Orquestrador: Iniciando novo scan de rede...)")
        
        with lock:
            runtime_timeout = shared_state.get('scan_timeout', config.SCAN_TIMEOUT)
            override_network = shared_state.get('network_cidr')
            config.SNMP_VERSION = shared_state.get('snmp_version', config.SNMP_VERSION)
            config.SNMP_COMMUNITY = shared_state.get('snmp_community', config.SNMP_COMMUNITY)
            config.SNMP_TIMEOUT = shared_state.get('snmp_timeout', config.SNMP_TIMEOUT)
            config.SNMP_RETRIES = shared_state.get('snmp_retries', config.SNMP_RETRIES)
            config.SNMP_PORT = shared_state.get('snmp_port', config.SNMP_PORT)

        config.SCAN_TIMEOUT = runtime_timeout
        network_cidr = override_network or utils.detect_active_network()
        
        if not network_cidr:
            print("(Orquestrador: Erro - Não foi possível detectar a rede ativa.)")
            time.sleep(config.POLLING_INTERVAL_STABLE)
            continue
        
        # 1. Descoberta ARP e 2. Ping
        devices = discovery.discovery_arp(network_cidr)
        for device in devices:
            ping_result = discovery.discovery_ping(device['ip'])
            device.update(ping_result)
        
        # 3. Enriquecimento SNMP (Método Confiável e Único para 'Papel')
        print("(Orquestrador: Tentando enriquecer dispositivos online com SNMP...)")
        for device in devices:
            if device.get('status') == 'online':
                snmp_info = discovery.discovery_snmp_basic(device['ip'])
                if snmp_info:
                    device.update(snmp_info)

        # 4. Enriquecimento de Fabricante
        print("(Orquestrador: Consultando fabricantes dos endereços MAC localmente...)")
        from oui_db import OUI_DATABASE
        for device in devices:
            if 'mac' in device and device['mac']:
                try:
                    oui = device['mac'].replace(':', '').replace('-', '').upper()[:6]
                    vendor = OUI_DATABASE.get(oui, 'Desconhecido')
                    device['producer'] = vendor
                except Exception:
                    device['producer'] = 'N/A'
        
        # 5. Salvar no Banco de Dados
        database.salvar_resultado_scan(devices)
        print("(Orquestrador: Scan concluído. Resultados salvos no banco de dados.)")
        
        current_device_count = len(devices)
        with lock:
            interval_stable = shared_state.get('interval_stable', config.POLLING_INTERVAL_STABLE)
            interval_change = shared_state.get('interva l_change', config.POLLING_INTERVAL_CHANGE)
            
        if current_device_count != last_device_count:
            next_interval = interval_change
            print(f"(Orquestrador: Mudança detectada na rede. Próximo scan em {next_interval}s.)")
        else:
            next_interval = interval_stable
            print(f"(Orquestrador: Rede estável. Próximo scan em {next_interval}s.)")
        
        last_device_count = current_device_count

        with lock:
            shared_state['force_scan'] = False
            shared_state['device_count'] = current_device_count
        
        seconds_remaining = next_interval
        while seconds_remaining > 0:
            with lock:
                if not shared_state.get('running', True) or shared_state.get('status') == 'pausado' or shared_state.get('force_scan', False):
                    break
                shared_state['next_scan_in'] = seconds_remaining
            time.sleep(1)
            seconds_remaining -= 1

        # 6. Escrever o arquivo de status para o agente SNMP
        _write_status_file(shared_state, devices)


if __name__ == "__main__":
    # O estado inicial compartilhado não precisa de alterações
    shared_state = {
        'status': 'rodando',
        'running': True,
        'force_scan': True,
        'device_count': 0,
        'next_scan_in': 0,
        'interval_stable': config.POLLING_INTERVAL_STABLE,
        'interval_change': config.POLLING_INTERVAL_CHANGE,
        'scan_timeout': config.SCAN_TIMEOUT,
        'network_cidr': None,
        'snmp_version': config.SNMP_VERSION,
        'snmp_community': config.SNMP_COMMUNITY,
        'snmp_timeout': config.SNMP_TIMEOUT,
        'snmp_retries': config.SNMP_RETRIES,
        'snmp_port': config.SNMP_PORT,
    }

    thread_lock = threading.Lock()

    # A inicialização do DB agora chama a função simplificada
    database.inicializar_db()

    orchestrator_thread = threading.Thread(
        target=run_orchestrator,
        args=(shared_state, thread_lock),
        daemon=True
    )
    orchestrator_thread.start()

    shell = cli.ControlShell(shared_state)
    shell.cmdloop()

    print("Programa finalizado.")