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
from pathlib import Path

import cli
import config
import database
import discovery
import utils
from oui_db import OUI_DATABASE
from utils import get_default_gateway_ip  # Importação necessária para detecção de gateway


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
SNMP_DIR = PROJECT_ROOT / "T3_SNMP_Agente" / "snmp_agent"
STATUS_JSON_PATH = SNMP_DIR / "status.json"


def _write_status_file(shared_state, devices):
    """
    Escreve o estado atual e a lista de dispositivos em um arquivo JSON
    compatível com a AUTO-DISCOVERY-MIB.

    Estrutura esperada pelo agente SNMP:
    {
        "targetNetwork": "192.168.1.0/24",
        "silentMode": false,
        "scannerRunning": false,
        "lastScanStart": "2025-12-02 12:34:56",
        "lastScanEnd": "2025-12-02 12:35:42",
        "nextScanInSeconds": 30,
        "scansPerformedTotal": 5,
        "lastScanDeviceCount": 12,
        "devices": [
            {
                "ip": "192.168.1.1",
                "mac": "AA:BB:CC:DD:EE:FF",
                "status": "online",
                "manufacturer": "Cisco Systems",
                "role": "Roteador",
                "firstSeen": "2025-12-02 12:34:56",
                "ttl": 64,
                "snmpName": "Router-1",
                "openPorts": [22, 80, 443]
            }
        ]
    }
    """
    network_cidr = shared_state.get('network_cidr') or 'auto'
    silent_mode = bool(shared_state.get('silent_mode', False))
    scanner_running = bool(shared_state.get('scanner_running', False))

    def _int_or_zero(value, default=0):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed >= 0 else default

    last_scan_start = shared_state.get('last_scan_start')
    if last_scan_start is None:
        last_scan_start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    last_scan_end = shared_state.get('last_scan_end')

    device_count = _int_or_zero(shared_state.get('device_count'), len(devices))
    next_scan_in = _int_or_zero(shared_state.get('next_scan_in'))
    scans_performed = _int_or_zero(shared_state.get('scans_performed'))

    status_data = {
        "targetNetwork": network_cidr,
        "silentMode": silent_mode,
        "scannerRunning": scanner_running,
        "lastScanStart": last_scan_start,
        "lastScanEnd": last_scan_end,
        "nextScanInSeconds": next_scan_in,
        "scansPerformedTotal": scans_performed,
        "lastScanDeviceCount": device_count,
        "devices": []
    }

    for device in devices:
        manufacturer = device.get('manufacturer') or device.get('producer') or ''
        role = device.get('role') or ''
        snmp_name = device.get('snmpName') or device.get('snmp_name') or ''
        ports_raw = device.get('openPorts', device.get('open_ports', []))
        if isinstance(ports_raw, list):
            ports_sanitized = []
            for port in ports_raw:
                try:
                    ports_sanitized.append(int(port))
                except (TypeError, ValueError):
                    continue
        elif isinstance(ports_raw, str):
            ports_sanitized = []
            for segment in ports_raw.split(','):
                try:
                    ports_sanitized.append(int(segment.strip()))
                except (TypeError, ValueError):
                    continue
        else:
            ports_sanitized = []

        ttl_value = device.get('ttl')
        try:
            ttl_sanitized = int(ttl_value) if ttl_value is not None else 0
        except (TypeError, ValueError):
            ttl_sanitized = 0
        ttl_sanitized = max(0, min(ttl_sanitized, 255))

        first_seen = (
            device.get('firstSeen')
            or device.get('first_seen')
            or device.get('discoveryTime')
            or last_scan_start
        )

        sanitized_device = {
            "ip": device.get('ip', ''),
            "mac": device.get('mac', ''),
            "status": device.get('status', 'offline'),
            "manufacturer": manufacturer[:64],
            "role": role,
            "firstSeen": first_seen,
            "ttl": ttl_sanitized,
            "snmpName": snmp_name,
            "snmpDescription": device.get('snmp_description', ''),
            "openPorts": ports_sanitized,
            "discoveryTime": device.get('discoveryTime', first_seen)
        }

        status_data["devices"].append(sanitized_device)
    try:
        STATUS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_JSON_PATH, 'w') as f:
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
            silent_mode = shared_state.get('silent_mode', False)

        if is_paused and not is_forced:
            time.sleep(1)
            continue
        
        if not silent_mode:
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
            if not silent_mode:
                print("(Orquestrador: Erro - Não foi possível detectar a rede ativa.)")
            time.sleep(config.POLLING_INTERVAL_STABLE)
            continue

        scan_started_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        with lock:
            shared_state['last_scan_start'] = scan_started_at
            shared_state['scanner_running'] = True
            shared_state['next_scan_in'] = 0
        
        devices = []
        try:
            # Obtenha o gateway no início de cada scan
            default_gateway = get_default_gateway_ip()
            if not silent_mode:
                print(f"(Orquestrador: Gateway padrão detectado: {default_gateway})")

            # 1. Descoberta ARP
            devices = discovery.discovery_arp(network_cidr)

            # 2. Ping e Definição de Status (LÓGICA ATUALIZADA)
            if not silent_mode:
                print("(Orquestrador: Verificando status dos dispositivos via Ping...)")
            for device in devices:
                ping_result = discovery.discovery_ping(device['ip'])

                if ping_result.get('status') == 'online':
                    device.update(ping_result)  # Adiciona status e ttl
                else:
                    # Se o ping falhou, o dispositivo está "não responsivo"
                    device['status'] = 'unresponsive'
                    device['ttl'] = None

            # 3. Scan de Portas (NOVO BLOCO)
            if not silent_mode:
                print("(Orquestrador: Verificando portas abertas em dispositivos online...)")
            for device in devices:
                if device.get('status') == 'online':
                    port_results = discovery.discovery_tcp_ports(device['ip'])
                    device.update(port_results)
                else:
                    # Dispositivos unresponsive não têm portas abertas
                    device['open_ports'] = []

            # 4. Classificação de Papel (LÓGICA REFINADA)
            if not silent_mode:
                print("(Orquestrador: Classificando papéis com lógica refinada...)")

            network_vendors = {'cisco', 'ubiquiti', 'palo alto'}

            for device in devices:
                ip = device.get('ip')
                ports = set(device.get('open_ports', []))
                producer = (device.get('producer') or '').lower()
                ttl = device.get('ttl')

                # 1. Regra do Gateway (Prioridade Máxima - sempre Roteador)
                if ip == default_gateway:
                    device['role'] = 'Roteador'
                    continue

                # 2. Regras baseadas em Portas e Fabricante
                role_found = False
                if ports:
                    if (22 in ports or 23 in ports) and any(vendor in producer for vendor in network_vendors):
                        device['role'] = 'Switch Gerenciável'
                        role_found = True
                    elif (80 in ports or 443 in ports) and 'ubiquiti' in producer:
                        device['role'] = 'Access Point'
                        role_found = True
                    elif 3389 in ports:
                        device['role'] = 'Servidor Windows'
                        role_found = True
                    elif 80 in ports or 443 in ports:
                        device['role'] = 'Servidor Web'
                        role_found = True

                if role_found:
                    continue

                # 3. Regras de Fallback baseadas em TTL
                if ttl is not None:
                    if ttl <= 64:
                        device['role'] = 'Roteador'
                    else:
                        device['role'] = 'Host'
                else:
                    device['role'] = 'Host'

            # 5. Enriquecimento SNMP (sobrescreve o palpite do TTL, mas não o do gateway)
            if not silent_mode:
                print("(Orquestrador: Tentando enriquecer dispositivos online com SNMP...)")
            for device in devices:
                if device.get('status') == 'online':
                    # Não rodar SNMP no gateway se já o identificamos
                    if device.get('ip') == default_gateway:
                        continue

                    snmp_info = discovery.discovery_snmp_basic(device['ip'])
                    if snmp_info and snmp_info.get('role'):  # Se SNMP retornou um papel
                        device.update(snmp_info)  # Atualiza, sobrescrevendo o TTL
                    elif snmp_info:
                        # Atualiza outras informações SNMP mas mantém o role detectado
                        snmp_info_copy = snmp_info.copy()
                        snmp_info_copy.pop('role', None)
                        device.update(snmp_info_copy)

            # 6. Enriquecimento de Fabricante
            if not silent_mode:
                print("(Orquestrador: Consultando fabricantes dos endereços MAC localmente...)")
            for device in devices:
                if 'mac' in device and device['mac']:
                    try:
                        oui = device['mac'].replace(':', '').replace('-', '').upper()[:6]
                        vendor = OUI_DATABASE.get(oui, 'Desconhecido')
                        # Limita o nome do fabricante a 20 caracteres
                        if len(vendor) > 20:
                            vendor = vendor[:20]
                        device['producer'] = vendor
                    except Exception:
                        device['producer'] = 'N/A'

            # 7. Salvar no Banco de Dados
            database.salvar_resultado_scan(devices)
            if not silent_mode:
                print("(Orquestrador: Scan concluído. Resultados salvos no banco de dados.)")

            # 8. Incrementar contador de scans para a MIB SNMP
            with lock:
                shared_state['scans_performed'] = shared_state.get('scans_performed', 0) + 1
        except Exception as e:
            if not silent_mode:
                print(f"(Orquestrador: Erro durante o scan: {e})")
            devices = []
        finally:
            with lock:
                shared_state['scanner_running'] = False
                shared_state['last_scan_end'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        current_device_count = len(devices)
        with lock:
            interval_stable = shared_state.get('interval_stable', config.POLLING_INTERVAL_STABLE)
            interval_change = shared_state.get('interval_change', config.POLLING_INTERVAL_CHANGE)
            
        if current_device_count != last_device_count:
            next_interval = interval_change
            if not silent_mode:
                print(f"(Orquestrador: Mudança detectada na rede. Próximo scan em {next_interval}s.)")
        else:
            next_interval = interval_stable
            if not silent_mode:
                print(f"(Orquestrador: Rede estável. Próximo scan em {next_interval}s.)")
        
        last_device_count = current_device_count

        with lock:
            shared_state['force_scan'] = False
            shared_state['device_count'] = current_device_count
            shared_state['scanner_running'] = False
        
        # Escrever arquivo de status para o agente SNMP (imediatamente após o scan)
        _write_status_file(shared_state, devices)
        
        seconds_remaining = next_interval
        while seconds_remaining > 0:
            with lock:
                if not shared_state.get('running', True) or shared_state.get('status') == 'pausado' or shared_state.get('force_scan', False):
                    break
                shared_state['next_scan_in'] = seconds_remaining
            time.sleep(1)
            seconds_remaining -= 1

        # Atualizar status.json com o tempo restante atualizado
        _write_status_file(shared_state, devices)


if __name__ == "__main__":
    # O estado inicial compartilhado não precisa de alterações
    shared_state = {
        'status': 'rodando',
        'running': True,
        'force_scan': True,
        'device_count': 0,
        'next_scan_in': 0,
        'scans_performed': 0,  # Contador total de scans realizados (para SNMP MIB)
        'scanner_running': False,
        'last_scan_start': None,
        'last_scan_end': None,
        'interval_stable': config.POLLING_INTERVAL_STABLE,
        'interval_change': config.POLLING_INTERVAL_CHANGE,
        'scan_timeout': config.SCAN_TIMEOUT,
        'network_cidr': None,
        'snmp_version': config.SNMP_VERSION,
        'snmp_community': config.SNMP_COMMUNITY,
        'snmp_timeout': config.SNMP_TIMEOUT,
        'snmp_retries': config.SNMP_RETRIES,
        'snmp_port': config.SNMP_PORT,
        'silent_mode': False,
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