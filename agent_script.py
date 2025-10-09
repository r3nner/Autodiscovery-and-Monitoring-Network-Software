#!/usr/bin/env python3
# agent_script.py

import sys
import json
import time
import os 

# Constrói o caminho absoluto para o status.json, baseado na localização deste script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = "/home/andre/Documents/Andre/4° Semestre/Gerenciamento de Redes 'A'/T1 - Autodescoberta de Rede/status.json"
# --- FIM DA CORREÇÃO ---

# OID base da  MIB
BASE_OID = ".1.3.6.1.3.9999.1"

# Mapeamento de OIDs para chaves no JSON
OID_MAP = {
    f"{BASE_OID}.1.1.0": ("control", "targetNetwork"),
    f"{BASE_OID}.2.1.0": ("status", "nextScanInSeconds"),
    f"{BASE_OID}.2.2.0": ("status", "lastScanDeviceCount"),
}

# OIDs da tabela de dispositivos
DEVICE_TABLE_OID_BASE = f"{BASE_OID}.3.1.1"
DEVICE_COLUMNS = {
    "2": ("ip", "IpAddress"),
    "3": ("mac", "OctetString"),
    "4": ("status_val", "Integer"),
    "5": ("producer", "OctetString"),
    "6": ("role", "OctetString"),
}

def get_status_data():
    """Lê e carrega os dados do arquivo de status JSON."""
    try:
        with open(STATUS_FILE, 'r') as f:
            data = json.load(f)
            # Pre-processar alguns valores
            for dev in data.get('devices', []):
                dev['status_val'] = 1 if dev.get('status') == 'online' else 2
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def handle_request(oid):
    """Processa uma requisição GET/GETNEXT para um OID."""
    data = get_status_data()
    if not data:
        return None

    # Verifica se é um OID escalar
    if oid in OID_MAP:
        group, key = OID_MAP[oid]
        value = data.get(group, {}).get(key)
        if value is not None:
            oid_type = "OctetString" if isinstance(value, str) else "Gauge32"
            return oid, oid_type, str(value)

    # Lógica para a tabela
    if oid.startswith(DEVICE_TABLE_OID_BASE):
        parts = oid.replace(DEVICE_TABLE_OID_BASE + '.', '').split('.')
        if len(parts) == 2:
            col_id, row_idx_str = parts
            row_idx = int(row_idx_str) - 1
            devices = data.get('devices', [])
            
            if col_id in DEVICE_COLUMNS and 0 <= row_idx < len(devices):
                key, oid_type = DEVICE_COLUMNS[col_id]
                value = devices[row_idx].get(key, "N/A")
                return oid, oid_type, str(value)
    
    return None

def main():
    """Loop principal para o script pass_persist."""
    try:
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                time.sleep(0.1)
                continue

            if line.upper() == "PING":
                sys.stdout.write("PONG\n")
            elif line.upper() in ["GET", "GETNEXT"]:
                oid = sys.stdin.readline().strip()
                result = handle_request(oid)
                if result:
                    found_oid, oid_type, value = result
                    sys.stdout.write(f"{found_oid}\n")
                    sys.stdout.write(f"{oid_type}\n")
                    sys.stdout.write(f"{value}\n")
            sys.stdout.flush()

    except Exception:
        pass

if __name__ == "__main__":
    main()